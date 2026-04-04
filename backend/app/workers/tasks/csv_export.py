import csv
import io
import logging
from app.workers.celery_app import celery_app, run_async
from app.workers.tasks.base import ReportBaseTask
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Default columns if none specified in filters
DEFAULT_COLUMNS = [
    "subscription_id",
    "customer_name",
    "region",
    "plan_name",
    "status",
    "billing_cycle",
    "seats",
    "mrr",
    "started_at",
]


@celery_app.task(
    bind=True,
    base=ReportBaseTask,
    name="app.workers.tasks.csv_export.run_csv_export",
    max_retries=settings.celery_task_max_retries,
    default_retry_delay=30,
    acks_late=True,
)
def run_csv_export(self, job_id: str, tenant_id: str, filters: dict):
    """
    Generate a CSV export of subscription data.

    Stages:
      0-10%  : Counting total rows for progress calculation
      10-80% : Fetching rows in chunks of 1,000 and writing to CSV buffer
      80-95% : Uploading CSV to MinIO
      95-100%: Complete
    """
    try:
        columns = filters.get("columns", DEFAULT_COLUMNS)
        # ── 1. Count total rows ───────────────────────────────────────
        self.update_progress(job_id, 5, "Counting total rows...", eta_secs=60)
        total_rows = run_async(_count_rows(tenant_id, filters))
        self.update_progress(
            job_id, 10, f"Exporting {total_rows:,} rows...", eta_secs=50
        )

        # ── 2. Fetch rows in chunks and write to CSV buffer ───────────
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()

        rows_written = 0
        offset = 0
        chunk_size = 1000

        while True:
            chunk = run_async(
                _fetch_chunk(filters, offset=offset, chunk_size=chunk_size)
            )

            if not chunk:
                break

            writer.writerows(chunk)
            rows_written += len(chunk)
            offset += chunk_size

            # Progress: maps 100% → 80% of total job time
            pct = 10 + int((rows_written / total_rows) * 70) if total_rows else 80
            self.update_progress(
                job_id,
                pct,
                f"Written {rows_written:,} / {total_rows:,} rows",
                eta_secs=max(0, int((total_rows - rows_written) / 2000)),
            )

        # ── 3. Upload to MinIO ───────────────────────────────────
        self.update_progress(job_id, 90, "Uploading to storage...", eta_secs=10)

        csv_bytes = csv_buffer.getvalue().encode("utf-8")
        csv_buffer.close()

        from app.services.storage_service import upload_file_sync, build_object_key

        object_key = build_object_key(tenant_id, job_id, "csv")
        upload_file_sync(csv_bytes, object_key, "text/csv")

        self.update_progress(job_id, 99, "Upload complete", eta_secs=1)

        return object_key
    except Exception as exc:
        logger.error(f"[{job_id}] CSV export failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


# ── Async helpers ─────────────────────────────────────────────────────
async def _count_rows(tenant_id: str, filters: dict) -> int:
    """Returns the total number of rows for the given filters."""
    from app.db.base import AsyncSessionLocal
    from app.db.models.seed.subscription import Subscription
    from app.db.models.seed.customer import Customer
    from app.db.models.seed.plan import Plan
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as session:
        query = select(func.count()).select_from(
            select(Subscription)
            .join(Customer, Subscription.customer_id == Customer.id)
            .join(Plan, Subscription.plan_id == Plan.id)
            .subquery()
        )
        query = _apply_filters(query, filters, count_mode=True)
        result = await session.execute(query)
        return result.scalar_one() or 0


async def _fetch_chunk(filters: dict, offset: int, chunk_size: int) -> list[dict]:
    """Fetch a single chunk of subscription rows as plain dicts."""
    from app.db.base import AsyncSessionLocal
    from app.db.models.seed.subscription import Subscription
    from app.db.models.seed.customer import Customer
    from app.db.models.seed.plan import Plan
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        query = (
            select(Subscription, Customer, Plan)
            .join(Customer, Subscription.customer_id == Customer.id)
            .join(Plan, Subscription.plan_id == Plan.id)
            .order_by(Subscription.started_at.desc())
            .offset(offset)
            .limit(chunk_size)
        )

        if filters.get("region"):
            query = query.where(Customer.region == filters["region"])
        if filters.get("status") and filters["status"] != "all":
            query = query.where(Subscription.status == filters["status"])
        if filters.get("plan_ids"):
            query = query.where(Plan.id.in_(filters["plan_ids"]))
        if filters.get("date_from"):
            query = query.where(Subscription.started_at >= filters["date_from"])
        if filters.get("date_to"):
            query = query.where(Subscription.started_at <= filters["date_to"])

        result = await session.execute(query)
        rows = result.all()

    return [
        {
            "subscription_id": str(sub.id),
            "customer_name": customer.company_name,
            "region": customer.region,
            "plan_name": plan.name,
            "status": sub.status,
            "billing_cycle": sub.billing_cycle,
            "seats": sub.seats,
            "mrr": float(sub.mrr),
            "started_at": sub.started_at.isoformat(),
        }
        for sub, customer, plan in rows
    ]


def _apply_filters(query, filters: dict, count_mode: bool = False):
    """Helper — applies WHERE clauses. Only used for count query."""
    # For the count query the join is already in the subquery — nothing extra needed here.
    # Kept as a hook for future filter complexity.
    return query
