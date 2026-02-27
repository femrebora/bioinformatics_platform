"""Redis-backed job log buffer.

Pipeline tasks append log lines during execution.  The API endpoint
reads them on demand (polled by the frontend).  Keys expire after 24 h
so they don't accumulate indefinitely.
"""
import logging
from datetime import datetime, timezone

import redis as _redis_lib

from app.config import settings

logger = logging.getLogger(__name__)

_KEY_TTL = 86_400   # 24 hours
_MAX_LINES = 2_000  # cap stored lines per job to avoid unbounded growth


def _client() -> _redis_lib.Redis:
    return _redis_lib.from_url(settings.CELERY_BROKER_URL, decode_responses=True)


def append_log(job_id: str, line: str) -> None:
    """Append a timestamped log line to the job's log buffer.

    Silently swallows errors (log loss is preferable to task failure).
    """
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    entry = f"[{ts}] {line}"
    try:
        r = _client()
        key = f"job_logs:{job_id}"
        # RPUSH then trim so we never exceed _MAX_LINES
        pipe = r.pipeline()
        pipe.rpush(key, entry)
        pipe.ltrim(key, -_MAX_LINES, -1)
        pipe.expire(key, _KEY_TTL)
        pipe.execute()
    except Exception as exc:
        logger.debug("log_streamer.append_log failed for %s: %s", job_id, exc)


def get_logs(job_id: str, offset: int = 0) -> list[str]:
    """Return log lines from ``offset`` to the end of the buffer.

    Returns an empty list on any Redis error.
    """
    try:
        return _client().lrange(f"job_logs:{job_id}", offset, -1) or []
    except Exception as exc:
        logger.debug("log_streamer.get_logs failed for %s: %s", job_id, exc)
        return []


def log_count(job_id: str) -> int:
    """Return total number of stored log lines for a job."""
    try:
        return _client().llen(f"job_logs:{job_id}") or 0
    except Exception:
        return 0


def clear_logs(job_id: str) -> None:
    """Delete the log buffer for a job (e.g. on retry)."""
    try:
        _client().delete(f"job_logs:{job_id}")
    except Exception:
        pass
