"""
Lightweight Redis store for tracking AWS Batch job IDs.

When a direct Batch job is submitted (BioScript, Custom, Snakemake wrappers),
the runner saves the Batch job ID here.  The cancel endpoint can then call
batch.terminate_job() to stop the Batch job as well as the Celery task.

The key expires after 24 hours — well beyond any realistic job duration.
"""
import logging

import redis

from app.config import settings

logger = logging.getLogger(__name__)

_KEY_TTL = 86_400  # 24 hours


def _redis():
    return redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)


def set_batch_job_id(job_id: str, batch_job_id: str) -> None:
    """Persist the AWS Batch job ID so it can be retrieved by the cancel endpoint."""
    try:
        _redis().setex(f"batch_job:{job_id}", _KEY_TTL, batch_job_id)
        logger.debug("[batch_tracker] stored batch_job_id=%s for job=%s", batch_job_id, job_id)
    except Exception as exc:
        logger.warning("[batch_tracker] failed to store batch_job_id: %s", exc)


def get_batch_job_id(job_id: str) -> str | None:
    """Return the AWS Batch job ID for the given platform job, or None."""
    try:
        val = _redis().get(f"batch_job:{job_id}")
        return val  # already str because decode_responses=True
    except Exception as exc:
        logger.warning("[batch_tracker] failed to get batch_job_id: %s", exc)
        return None


def delete_batch_job_id(job_id: str) -> None:
    """Clean up the tracking key once the job is done."""
    try:
        _redis().delete(f"batch_job:{job_id}")
    except Exception:
        pass
