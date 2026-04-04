import logging
import redis as _redis
from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

MAX_CONCURRENT_JOBS = settings.max_concurrent_jobs_per_user  # default: 5


def check_and_increment_active_jobs(user_id: str) -> bool:
    """
    Atomically increment the active job counter for a user.
    Returns True if the job is allowed (counter ≤ limit after increment).
    Returns False if the limit is exceeded — caller must return HTTP 429.

    The counter has a 1-hour TTL as a safety net against orphaned counts
    (e.g. worker crash mid-job before decrement runs).
    """
    r = _redis.Redis.from_url(settings.redis_url)
    key = f"ratelimit:{user_id}:active_jobs"

    try:
        current = r.incr(key)
        # Set TTL on first creation (safety net — jobs shouldn't last > 1 hour)
        if current == 1:
            r.expire(key, 3600)

        if current > MAX_CONCURRENT_JOBS:
            # Undo the increment — this request is rejected
            r.decr(key)
            return False

        return True
    finally:
        r.close()


def get_active_job_count(user_id: str) -> int:
    """Read the current active job count for a user without modifying it."""
    r = _redis.Redis.from_url(settings.redis_url)
    try:
        val = r.get(f"ratelimit:{user_id}:active_jobs")
        return int(val) if val else 0
    finally:
        r.close()


def decrement_active_jobs(user_id: str):
    """
    Decrement the active-job counter for a user on Redis DB 0 (redis_url).
    Must target the same DB that rate_limit.py uses when incrementing —
    that's DB 0, NOT the pubsub DB (DB 1).
    Guards against the counter going negative (e.g. worker crash mid-job).
    """
    r = _redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        current = r.decr(f"ratelimit:{user_id}:active_jobs")
        if current < 0:
            logger.warning(f"Active jobs counter is negative: {current}")
            r.set(f"ratelimit:{user_id}:active_jobs", 0)
    except Exception as e:
        logger.error(f"Failed to decrement active jobs counter: {e}")
    finally:
        r.close()
