import asyncio

from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown
from kombu import Queue, Exchange
from app.core.config import get_settings
from celery.schedules import crontab

settings = get_settings()

_worker_loop: asyncio.AbstractEventLoop | None = None

# Create the Celery app instance
celery_app = Celery(
    "reportflow",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.tasks.sales_summary",  # phase 1
        "app.workers.tasks.csv_export",  # phase 3
        "app.workers.tasks.pdf_report",  # phase 3
        "app.workers.tasks.beat_schedule",  # phase 5
        "app.workers.tasks.cleanup_jobs",  # job retention cleanup
    ],
)

# ── Queue definitions ───────────────────────────────────────────────
# Using explicit Queue objects lets us set delivery_mode (persistent)
# and ensures queues exist before workers start consuming

default_exchange = Exchange("reportflow", type="direct")

celery_app.conf.task_queues = (
    Queue(
        "default",
        default_exchange,
        routing_key="default",
        queue_arguments={"x-max-priority": 10},
    ),
    Queue(
        "high",
        default_exchange,
        routing_key="high",
        queue_arguments={"x-max-priority": 10},
    ),
    Queue(
        "low",
        default_exchange,
        routing_key="low",
        queue_arguments={"x-max-priority": 10},
    ),
)

celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "reportflow"
celery_app.conf.task_default_routing_key = "default"

# Serialization
# JSON is safer than pickle(default)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]

# Reliability settings
celery_app.conf.task_acks_late = True  # task is acknowledged after result is set
celery_app.conf.task_reject_on_worker_lost = (
    True  # task is re-queued if worker disconnects
)
# celery_app.conf.task_track_started = True # task is tracked as started when it starts running

# Timeout
celery_app.conf.task_time_limit = settings.celery_task_timeout_seconds
celery_app.conf.task_soft_time_limit = (
    settings.celery_task_timeout_seconds - 60
)  # warns a minute before hard timeout

# Result_expiry
celery_app.conf.result_expires = 60 * 60 * 24  # 24 hours


celery_app.conf.beat_schedule = {
    "dispatch-scheduled-jobs": {
        "task": "app.workers.tasks.beat_schedule.dispatch_scheduled_jobs",
        "schedule": settings.beat_schedule_interval,  # configurable via BEAT_SCHEDULE_INTERVAL env var
        "options": {
            "queue": "low",
            "priority": 9,  # lowest priority — never starve real report jobs
        },
    },
    "cleanup-old-jobs": {
        "task": "app.workers.tasks.cleanup_jobs.cleanup_old_jobs",
        "schedule": crontab(hour=3, minute=0),  # Daily at 03:00 UTC
        "options": {
            "queue": "low",
            "priority": 9,
        },
    },
}
celery_app.conf.timezone = "UTC"


# Tasks routing helper
PRIORITY_TO_QUEUE = {
    1: "high",
    2: "high",
    3: "default",
    4: "default",
    5: "default",
    6: "default",
    7: "low",
    8: "low",
    9: "low",
}


def get_queue_for_priority(priority: int) -> str:
    """Map job priority (1-9) to a Celery queue name."""
    return PRIORITY_TO_QUEUE.get(priority, "default")


def get_worker_loop() -> asyncio.AbstractEventLoop:
    """Return the persistent worker loop, creating one lazily if needed."""
    global _worker_loop

    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    return _worker_loop


def run_async(coro):
    """Run a coroutine on the worker's persistent event loop."""
    return get_worker_loop().run_until_complete(coro)


@worker_process_init.connect
def init_worker_loop(**kwargs):
    """Initialise a fresh event loop and DB pool for each Celery worker process."""
    global _worker_loop

    from app.db.base import engine

    _worker_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_worker_loop)
    _worker_loop.run_until_complete(engine.dispose())


@worker_process_shutdown.connect
def shutdown_worker_loop(**kwargs):
    """Dispose DB resources and close the worker event loop on shutdown."""
    global _worker_loop

    if _worker_loop is None or _worker_loop.is_closed():
        return

    from app.db.base import engine

    try:
        _worker_loop.run_until_complete(engine.dispose())
    finally:
        _worker_loop.close()
        asyncio.set_event_loop(None)
        _worker_loop = None
