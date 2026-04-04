import io
import logging
from datetime import datetime
from app.workers.celery_app import celery_app, run_async
from app.workers.tasks.base import ReportBaseTask
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@celery_app.task(
    bind=True,
    base=ReportBaseTask,
    name="app.workers.tasks.pdf_report.run_pdf_report",
    max_retries=settings.celery_task_max_retries,
    default_retry_delay=30,
    acks_late=True,
)
def run_pdf_report(self, job_id: str, tenant_id: str, filters: dict):
    """
    Generate a multi-section PDF report with charts.

    Stages:
      0-25%  : Fetch subscription data
      25-45% : Aggregate and compute section data
      45-60% : Render matplotlib charts to SVG
      60-85% : Render Jinja2 HTML template
      85-95% : Write PDF via WeasyPrint
      95-100%: Upload to MinIO
    """
    try:
        # ── Stage 1: Fetch data ──────────────────────────────────────
        self.update_progress(job_id, 5, "Connecting to database...", eta_secs=120)

        # Reuse the same fetch function as sales_summary
        from app.workers.tasks.sales_summary import _fetch_subscription_data
        data = run_async(_fetch_subscription_data(filters))
        self.update_progress(job_id, 25, f"Fetched {len(data['subscriptions'])} subscriptions", eta_secs=90)

        # ── Stage 2: Build section data ──────────────────────────────
        self.update_progress(job_id, 30, "Computing section data...", eta_secs=75)
        sections = _build_sections(data)
        self.update_progress(job_id, 45, "Section data ready", eta_secs=60)

        # ── Stage 3: Render charts ───────────────────────────────────
        self.update_progress(job_id, 48, "Rendering charts...", eta_secs=45)
        charts = _render_charts(sections)
        self.update_progress(job_id, 60, "Charts rendered", eta_secs=30)

        # ── Stage 4: Render HTML ─────────────────────────────────────
        self.update_progress(job_id, 62, "Rendering report layout...", eta_secs=25)
        html_content = _render_html(sections, charts, filters)
        self.update_progress(job_id, 80, "Layout complete", eta_secs=15)

        # ── Stage 5: Write PDF ───────────────────────────────────────
        self.update_progress(job_id, 82, "Converting to PDF...", eta_secs=10)
        pdf_bytes = _write_pdf(html_content)
        self.update_progress(job_id, 93, "PDF ready", eta_secs=4)

        # ── Stage 6: Upload ──────────────────────────────────────────
        self.update_progress(job_id, 95, "Uploading to storage...", eta_secs=2)
        from app.services.storage_service import upload_file_sync, build_object_key
        object_key = build_object_key(tenant_id, job_id, "pdf")
        upload_file_sync(pdf_bytes, object_key, content_type="application/pdf")

        self.update_progress(job_id, 99, "Upload complete", eta_secs=1)
        return object_key

    except Exception as exc:
        logger.error(f"[{job_id}] pdf_report failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


# ── Section data ─────────────────────────────────────────────────────

def _build_sections(data: dict) -> dict:
    """
    Build structured data for each report section from raw subscription rows.
    Returns a dict with keys: executive, mrr_breakdown, customer_table, churn.
    """
    subs = data["subscriptions"]
    active = [s for s in subs if s["status"] == "active"]
    cancelled = [s for s in subs if s["status"] == "cancelled"]
    trialing = [s for s in subs if s["status"] == "trialing"]

    total_mrr = sum(s["mrr"] for s in active)
    churned_mrr = sum(s["mrr"] for s in cancelled)

    # MRR by plan
    mrr_by_plan: dict[str, float] = {}
    for s in active:
        mrr_by_plan[s["plan_name"]] = mrr_by_plan.get(s["plan_name"], 0) + s["mrr"]

    # MRR by region
    mrr_by_region: dict[str, float] = {}
    for s in active:
        mrr_by_region[s["region"]] = mrr_by_region.get(s["region"], 0) + s["mrr"]

    # Customer table (top 20 by MRR)
    customer_mrr: dict[str, dict] = {}
    for s in active:
        name = s["customer_name"]
        if name not in customer_mrr:
            customer_mrr[name] = {"name": name, "region": s["region"], "plan": s["plan_name"], "mrr": 0.0}
        customer_mrr[name]["mrr"] += s["mrr"]

    top_customers = sorted(customer_mrr.values(), key=lambda x: x["mrr"], reverse=True)[:20]
    for c in top_customers:
        c["mrr"] = round(c["mrr"], 2)

    # Churn analysis
    churn_by_plan: dict[str, int] = {}
    for s in cancelled:
        churn_by_plan[s["plan_name"]] = churn_by_plan.get(s["plan_name"], 0) + 1

    return {
        "executive": {
            "total_mrr": round(total_mrr, 2),
            "churned_mrr": round(churned_mrr, 2),
            "net_mrr": round(total_mrr - churned_mrr, 2),
            "active_count": len(active),
            "cancelled_count": len(cancelled),
            "trialing_count": len(trialing),
            "total_count": len(subs),
        },
        "mrr_breakdown": {
            "by_plan": {k: round(v, 2) for k, v in sorted(mrr_by_plan.items(), key=lambda x: x[1], reverse=True)},
            "by_region": {k: round(v, 2) for k, v in sorted(mrr_by_region.items())},
        },
        "customer_table": top_customers,
        "churn": {
            "total_churned": len(cancelled),
            "churned_mrr": round(churned_mrr, 2),
            "by_plan": churn_by_plan,
            "churn_rate_pct": round((len(cancelled) / max(len(subs), 1)) * 100, 1),
        },
        "generated_at": datetime.utcnow().isoformat(),
    }


# ── Chart rendering ──────────────────────────────────────────────────

def _render_charts(sections: dict) -> dict:
    """
    Render matplotlib charts as SVG strings.
    Returns a dict of chart_name → svg_string.
    """
    import matplotlib
    matplotlib.use("Agg")   # non-interactive backend — required in a worker process
    import matplotlib.pyplot as plt

    charts = {}

    # Chart 1: MRR by Plan (horizontal bar)
    by_plan = sections["mrr_breakdown"]["by_plan"]
    if by_plan:
        fig, ax = plt.subplots(figsize=(8, max(3, len(by_plan) * 0.6)))
        plans = list(by_plan.keys())
        values = [by_plan[p] for p in plans]
        bars = ax.barh(plans, values, color="#0f3460", edgecolor="white")
        ax.set_xlabel("Monthly Recurring Revenue (£)")
        ax.set_title("MRR by Plan")
        ax.bar_label(bars, labels=[f"£{v:,.0f}" for v in values], padding=5, fontsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        charts["mrr_by_plan"] = _fig_to_svg(fig)
        plt.close(fig)

    # Chart 2: MRR by Region (pie chart)
    by_region = sections["mrr_breakdown"]["by_region"]
    if by_region:
        fig, ax = plt.subplots(figsize=(6, 5))
        labels = list(by_region.keys())
        values = [by_region[r] for r in labels]
        colors = ["#0f3460", "#16213e", "#533483", "#e94560", "#a8dadc"][:len(labels)]
        ax.pie(values, labels=labels, colors=colors, autopct="%1.1f%%", startangle=140)
        ax.set_title("MRR by Region")
        charts["mrr_by_region"] = _fig_to_svg(fig)
        plt.close(fig)

    return charts


def _fig_to_svg(fig) -> str:
    """Convert a matplotlib figure to an SVG string."""
    svg_buffer = io.StringIO()
    fig.savefig(svg_buffer, format="svg", bbox_inches="tight")
    svg_string = svg_buffer.getvalue()
    svg_buffer.close()
    # Strip the XML declaration so it embeds cleanly in HTML
    if svg_string.startswith("<?xml"):
        svg_string = svg_string[svg_string.index("<svg"):]
    return svg_string


# ── HTML rendering ───────────────────────────────────────────────────

def _render_html(sections: dict, charts: dict, filters: dict) -> str:
    """Render the full report HTML using Jinja2."""
    from jinja2 import Environment, BaseLoader

    env = Environment(loader=BaseLoader())
    template = env.from_string(_get_template())
    return template.render(
        sections=sections,
        charts=charts,
        filters=filters,
    )


def _get_template() -> str:
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body { font-family: Arial, sans-serif; margin: 40px; color: #2c2c2c; font-size: 13px; }
  h1 { color: #0f3460; border-bottom: 3px solid #0f3460; padding-bottom: 12px; font-size: 26px; }
  h2 { color: #0f3460; margin-top: 35px; font-size: 18px; border-left: 4px solid #0f3460; padding-left: 10px; }
  h3 { color: #16213e; font-size: 14px; margin-top: 20px; }

  .meta { color: #777; font-size: 11px; margin-bottom: 30px; }

  /* Executive summary cards */
  .kpi-grid { display: flex; flex-wrap: wrap; gap: 16px; margin: 20px 0; }
  .kpi-card {
    background: #f4f7ff; border-radius: 8px; padding: 18px 22px;
    flex: 1; min-width: 140px; text-align: center;
  }
  .kpi-card .value { font-size: 26px; font-weight: bold; color: #0f3460; }
  .kpi-card .label { font-size: 11px; color: #666; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
  .kpi-card.negative .value { color: #c0392b; }
  .kpi-card.positive .value { color: #27ae60; }

  /* Charts */
  .chart-row { display: flex; gap: 30px; margin: 20px 0; align-items: flex-start; }
  .chart-block { flex: 1; }
  .chart-block svg { max-width: 100%; height: auto; }

  /* Tables */
  table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 12px; }
  th { background: #0f3460; color: white; padding: 9px 10px; text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }
  td { padding: 7px 10px; border-bottom: 1px solid #eee; }
  tr:nth-child(even) { background: #f9f9f9; }
  .amount { text-align: right; font-family: monospace; }

  /* Churn section */
  .churn-summary { background: #fff5f5; border-left: 4px solid #c0392b; padding: 15px 20px; margin: 15px 0; border-radius: 4px; }
  .churn-rate { font-size: 32px; font-weight: bold; color: #c0392b; }

  .footer { margin-top: 50px; font-size: 10px; color: #aaa; text-align: center; border-top: 1px solid #eee; padding-top: 12px; }

  @media print { .page-break { page-break-before: always; } }
</style>
</head>
<body>

<h1>ReportFlow — Subscription Report</h1>
<p class="meta">
  Generated: {{ sections.generated_at }}
  {% if filters.region %} · Region: {{ filters.region }}{% endif %}
  {% if filters.status and filters.status != 'all' %} · Status: {{ filters.status }}{% endif %}
</p>

<!-- ── Section 1: Executive Summary ── -->
<h2>Executive Summary</h2>
<div class="kpi-grid">
  <div class="kpi-card positive">
    <div class="value">£{{ "{:,.0f}".format(sections.executive.total_mrr) }}</div>
    <div class="label">Total MRR</div>
  </div>
  <div class="kpi-card negative">
    <div class="value">£{{ "{:,.0f}".format(sections.executive.churned_mrr) }}</div>
    <div class="label">Churned MRR</div>
  </div>
  <div class="kpi-card positive">
    <div class="value">£{{ "{:,.0f}".format(sections.executive.net_mrr) }}</div>
    <div class="label">Net MRR</div>
  </div>
  <div class="kpi-card">
    <div class="value">{{ sections.executive.active_count }}</div>
    <div class="label">Active</div>
  </div>
  <div class="kpi-card">
    <div class="value">{{ sections.executive.trialing_count }}</div>
    <div class="label">Trialing</div>
  </div>
  <div class="kpi-card negative">
    <div class="value">{{ sections.executive.cancelled_count }}</div>
    <div class="label">Cancelled</div>
  </div>
</div>

<!-- ── Section 2: MRR Breakdown ── -->
<h2>MRR Breakdown</h2>
<div class="chart-row">
  {% if charts.mrr_by_plan %}
  <div class="chart-block">
    <h3>By Plan</h3>
    {{ charts.mrr_by_plan | safe }}
  </div>
  {% endif %}
  {% if charts.mrr_by_region %}
  <div class="chart-block">
    <h3>By Region</h3>
    {{ charts.mrr_by_region | safe }}
  </div>
  {% endif %}
</div>

<!-- ── Section 3: Top Customers ── -->
<div class="page-break"></div>
<h2>Top 20 Customers by MRR</h2>
<table>
  <thead>
    <tr>
      <th>#</th>
      <th>Company</th>
      <th>Region</th>
      <th>Plan</th>
      <th class="amount">Monthly MRR</th>
    </tr>
  </thead>
  <tbody>
    {% for c in sections.customer_table %}
    <tr>
      <td>{{ loop.index }}</td>
      <td>{{ c.name }}</td>
      <td>{{ c.region }}</td>
      <td>{{ c.plan }}</td>
      <td class="amount">£{{ "{:,.2f}".format(c.mrr) }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<!-- ── Section 4: Churn Analysis ── -->
<h2>Churn Analysis</h2>
<div class="churn-summary">
  <div class="churn-rate">{{ sections.churn.churn_rate_pct }}%</div>
  <div>Overall churn rate · {{ sections.churn.total_churned }} cancelled subscriptions · £{{ "{:,.0f}".format(sections.churn.churned_mrr) }} churned MRR</div>
</div>

{% if sections.churn.by_plan %}
<h3>Cancellations by Plan</h3>
<table>
  <thead>
    <tr><th>Plan</th><th class="amount">Cancellations</th></tr>
  </thead>
  <tbody>
    {% for plan, count in sections.churn.by_plan.items() | sort(attribute='1', reverse=True) %}
    <tr>
      <td>{{ plan }}</td>
      <td class="amount">{{ count }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endif %}

<p class="footer">ReportFlow · Report generated {{ sections.generated_at }} · Confidential</p>
</body>
</html>
"""


# ── PDF export ───────────────────────────────────────────────────────

def _write_pdf(html_content: str) -> bytes:
    """Render HTML string to PDF bytes using WeasyPrint."""
    from weasyprint import HTML
    return HTML(string=html_content).write_pdf()