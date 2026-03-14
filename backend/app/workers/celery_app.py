from celery import Celery
from kombu import Queue, Exchange
from app.core.config import get_settings

settings = get_settings()

# Create the Celery app instance
celery_app = Celery(
    "reportflow",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.tasks.sales_summary",  # phase 1
        # "app.workers.tasks.csv_export",  # phase 3
        # "app.workers.tasks.pdf_report",  # phase 3
    ],
)

# ── Queue definitions ───────────────────────────────────────────────
# Using explicit Queue objects lets us set delivery_mode (persistent)
# and ensures queues exist before workers start consuming

default_exchange = Exchange('reportflow', type='direct')

celery_app.conf.task_queues = (
    Queue('default', default_exchange, routing_key='default', queue_arguments={'x-max-priority': 10}),
    Queue('high', default_exchange, routing_key='high', queue_arguments={'x-max-priority': 10}),
    Queue('low', default_exchange, routing_key='low', queue_arguments={'x-max-priority': 10}),
)

celery_app.conf.task_default_queue = 'default'
celery_app.conf.task_default_exchange = 'reportflow'
celery_app.conf.task_default_routing_key = 'default'

# Serialization
# JSON is safer than pickle(default)
celery_app.conf.task_serializer = 'json'
celery_app.conf.result_serializer = 'json'
celery_app.conf.accept_content = ['json']

# Reliability settings
celery_app.conf.task_acks_late = True # task is acknowledged after result is set
celery_app.conf.task_reject_on_worker_lost = True # task is re-queued if worker disconnects
# celery_app.conf.task_track_started = True # task is tracked as started when it starts running

# Timeout
celery_app.conf.task_time_limit = settings.celery_task_timeout_seconds 
celery_app.conf.task_soft_time_limit = settings.celery_task_timeout_seconds - 60 # warns a minute before hard timeout

# Result_expiry
celery_app.conf.result_expires = 60 * 60 * 24 # 24 hours

# Tasks routing helper
PRIORITY_TO_QUEUE = {
    1: 'high',
    2: 'high',
    3: 'default',
    4: 'default',
    5: 'default',
    6: 'default',
    7: 'low',
    8: 'low',
    9: 'low',
}

def get_queue_for_priority(priority: int) -> str:
    """Map job priority (1-9) to a Celery queue name."""
    return PRIORITY_TO_QUEUE.get(priority, "default")


# def route_task(name, args, kwargs, options, task=None, **kw):
#     priority = kwargs.get('priority', 5)
#     queue = PRIORITY_TO_QUEUE.get(priority, 'default')
#     return {'queue': queue}


