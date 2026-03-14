import logging 
from datetime import datetime, datetime, timezone
from decimal import Decimal
from sqlalchemy import select, func
from app.workers.celery_app import celery_app
from app.workers.tasks.base import ReportBaseTask
from app.core.config import get_settings
import asyncio

logger = logging.getLogger(__name__)
settings = get_settings()

@celery_app.task(
    bind=True,
    base=ReportBaseTask,
    name="app.workers.tasks.sales_summary.run_sales_summary",
    max_retries=settings.celery_task_max_retries,
    default_retry_delay=30,
    acks_late=True,
)
def run_sales_summary(self, job_id: str, tenant_id: str, filters: dict):
    """
    Generate a Sales Summary PDF report.

    Stages:
      0-30%  : Fetch subscription data from PostgreSQL
      30-70% : Aggregate MRR metrics
      70-90% : Render HTML template → PDF via WeasyPrint
      90-100%: Upload PDF to MinIO
    """
    try:
        # ── 1. Fetch subscription data ───────────────────────────────────
        self.update_progress(job_id, 5, "Connecting to database...", eta_secs=90)
        data = asyncio.run(_fetch_subscription_data(filters))
        self.update_progress(job_id, 30, f"Fetched {len(data['subscriptions'])} subscriptions", eta_secs=70)
        
        # ── 2. Aggregate MRR metrics ─────────────────────────────────────
        self.update_progress(job_id, 35, "Aggregating MRR metrics...", eta_secs=55)
        metrics = _aggregate_metrics(data)
        self.update_progress(job_id, 70, "Aggregation complete", eta_secs=35)
        
        # ── 3. Render PDF ───────────────────────────────────────
        self.update_progress(job_id, 75, "Rendering PDF ...", eta_secs=30)
        pdf_bytes = _render_pdf(metrics, filters)
        self.update_progress(job_id, 90, "PDF rendering complete", eta_secs=15)
        
        # ── 4. Upload to MinIO ───────────────────────────────────
        self.update_progress(job_id, 92, "Uploading to storage...", eta_secs=10)
        from app.services.storage_service import upload_file_sync, build_object_key
        object_key = build_object_key(tenant_id, job_id, "pdf")
        upload_file_sync(pdf_bytes, object_key, "application/pdf")
        self.update_progress(job_id, 99, "Upload complete", eta_secs=0)
        
        return object_key
    
    except Exception as exc:
        logger.error(f"[{job_id}] sales_summary failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)
    

async def _fetch_subscription_data(filters: dict) -> dict:
    """Fetch subscriptions with related customer and plan data."""
    from app.db.base import AsyncSessionLocal
    from app.db.models.seed.subscription import Subscription
    from app.db.models.seed.customer import Customer
    from app.db.models.seed.plan import Plan
    
    async with AsyncSessionLocal() as session:
        query = (
            select(Subscription, Customer, Plan)
            .join(Customer, Subscription.customer_id == Customer.id)
            .join(Plan, Subscription.plan_id == Plan.id)
        )
        
        # Apply filters
        if filters.get("date_from"):
            query = query.where(Subscription.start_date >= filters["date_from"])
        if filters.get("date_to"):
            query = query.where(Subscription.start_date <= filters["date_to"])
        if filters.get("region"):
            query = query.where(Customer.region == filters["region"])
        if filters.get("status") and filters["status"] != "all":
            query = query.where(Subscription.status == filters["status"])
        if filters.get("plan_ids"):
            query = query.where(Subscription.plan_id.in_(filters["plan_ids"]))
        
        result = await session.execute(query)
        rows = result.all()
        
        # Map rows to dict
        subscriptions = []
        for sub, customer, plan in rows:
            subscriptions.append({
                "id": str(sub.id),
            "status": sub.status,
            "mrr": float(sub.mrr),
            "billing_cycle": sub.billing_cycle,
            "seats": sub.seats,
            "started_at": sub.started_at.isoformat(),
            "plan_name": plan.name,
            "customer_name": customer.company_name,
            "region": customer.region,
            })
        
        return {
            "subscriptions": subscriptions,
        }
        
# Aggreation (pure python)

def _aggregate_metrics(data: dict) -> dict:
    """Aggregate MRR metrics from subscription data."""
    subscriptions = data["subscriptions"]
    total_mrr = sum(s["mrr"] for s in subscriptions if s["status"] == "active")
    churned_mrr = sum(s["mrr"] for s in subscriptions if s["status"] == "cancelled")
    
    # MRR by reion
    mrr_by_region: dict[str, float] = {}
    for s in subscriptions:
        if s["status"] != "active":
            continue
        mrr_by_region[s["region"]] = mrr_by_region.get(s["region"], 0) + s["mrr"]
        
    # MRR by plan
    mrr_by_plan: dict[str, float] = {}
    for s in subscriptions:
        if s["status"] != "active":
            continue
        mrr_by_plan[s["plan_name"]] = mrr_by_plan.get(s["plan_name"], 0) + s["mrr"]
        
    # Top 10 customers by MRR
    customer_mrr: dict[str, float] = {}
    for s in subscriptions:
        if s["status"] != "active":
            continue
        customer_mrr[s["customer_name"]] = customer_mrr.get(s["customer_name"], 0) + s["mrr"]
        
    top_customers = sorted(customer_mrr.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "total_mrr": round(total_mrr, 2),
        "churned_mrr": round(churned_mrr, 2),
        "net_mrr": round(total_mrr - churned_mrr, 2),
        "active_subscriptions": len([s for s in subscriptions if s["status"] == "active"]),
        "total_subscriptions": len(subscriptions),
        "mrr_by_region": {k: round(v, 2) for k, v in sorted(mrr_by_region.items())},
        "mrr_by_plan": {k: round(v, 2) for k, v in sorted(mrr_by_plan.items())},
        "top_customers": [{"name": k, "mrr": round(v, 2)} for k, v in top_customers],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    

# PDF rendering

def _render_pdf(metrics: dict, filters: dict) -> bytes:
    """Render metrics dict to a PDF using Jinja2 + WeasyPrint."""
    from jinja2 import Environment, BaseLoader
    from weasyprint import HTML

    template_str = _get_report_template()
    env = Environment(loader=BaseLoader())
    template = env.from_string(template_str)
    html_content = template.render(metrics=metrics, filters=filters)

    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes


def _get_report_template() -> str:
    """Inline Jinja2 HTML template for the sales summary PDF."""
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body { font-family: Arial, sans-serif; margin: 40px; color: #333; }
  h1 { color: #1a1a2e; border-bottom: 3px solid #0f3460; padding-bottom: 10px; }
  h2 { color: #0f3460; margin-top: 30px; }
  .metric-grid { display: flex; gap: 20px; margin: 20px 0; }
  .metric-card {
    background: #f0f4ff; border-radius: 8px; padding: 20px;
    flex: 1; text-align: center;
  }
  .metric-card .value { font-size: 28px; font-weight: bold; color: #0f3460; }
  .metric-card .label { font-size: 13px; color: #666; margin-top: 5px; }
  table { width: 100%; border-collapse: collapse; margin-top: 15px; }
  th { background: #0f3460; color: white; padding: 10px; text-align: left; }
  td { padding: 8px 10px; border-bottom: 1px solid #eee; }
  tr:nth-child(even) { background: #f9f9f9; }
  .footer { margin-top: 40px; font-size: 11px; color: #999; text-align: center; }
</style>
</head>
<body>

<h1>Sales Summary Report</h1>
<p>Generated: {{ metrics.generated_at }}</p>

<h2>Key Metrics</h2>
<div class="metric-grid">
  <div class="metric-card">
    <div class="value">${{ "%.0f"|format(metrics.total_mrr) }}</div>
    <div class="label">Total MRR</div>
  </div>
  <div class="metric-card">
    <div class="value">${{ "%.0f"|format(metrics.churned_mrr) }}</div>
    <div class="label">Churned MRR</div>
  </div>
  <div class="metric-card">
    <div class="value">{{ metrics.active_subscriptions }}</div>
    <div class="label">Active Subscriptions</div>
  </div>
</div>

<h2>MRR by Region</h2>
<table>
  <tr><th>Region</th><th>MRR</th></tr>
  {% for region, mrr in metrics.mrr_by_region.items() %}
  <tr><td>{{ region }}</td><td>${{ "%.2f"|format(mrr) }}</td></tr>
  {% endfor %}
</table>

<h2>MRR by Plan</h2>
<table>
  <tr><th>Plan</th><th>MRR</th></tr>
  {% for plan, mrr in metrics.mrr_by_plan.items() %}
  <tr><td>{{ plan }}</td><td>${{ "%.2f"|format(mrr) }}</td></tr>
  {% endfor %}
</table>

<h2>Top 10 Customers by MRR</h2>
<table>
  <tr><th>Rank</th><th>Customer</th><th>MRR</th></tr>
  {% for customer in metrics.top_customers %}
  <tr>
    <td>{{ loop.index }}</td>
    <td>{{ customer.name }}</td>
    <td>${{ "%.2f"|format(customer.mrr) }}</td>
  </tr>
  {% endfor %}
</table>

<div class="footer">
  ReportFlow — Confidential — Generated automatically
</div>
</body>
</html>
"""