"""
Celery pipeline task.

Uses psycopg2 (sync) for DB access — Celery runs in a sync context.
DATABASE_URL in the worker env must use the postgresql+psycopg2 scheme
(docker-compose sets this automatically for the worker service).
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from app.celery_app import celery_app
from app.config import settings
from app.services.ec2.base import get_ec2_backend
from app.services.hla.base import get_hla_runner
from app.services.storage.base import get_storage_backend

logger = logging.getLogger(__name__)

# Build a sync DATABASE_URL — swap asyncpg driver for psycopg2
_sync_url = settings.DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
).replace(
    "postgresql://", "postgresql+psycopg2://"
)

_engine = create_engine(_sync_url, pool_pre_ping=True)


def _update_job(job_id: str, **kwargs) -> None:
    kwargs["updated_at"] = datetime.now(timezone.utc)
    set_clauses = ", ".join(f"{k} = :{k}" for k in kwargs)
    with _engine.begin() as conn:
        conn.execute(
            text(f"UPDATE jobs SET {set_clauses} WHERE id = :job_id"),
            {"job_id": job_id, **kwargs},
        )


def _get_job(job_id: str) -> dict:
    with _engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM jobs WHERE id = :job_id"),
            {"job_id": job_id},
        ).mappings().one()
    return dict(row)


@celery_app.task(bind=True, name="app.tasks.pipeline.run_hla_pipeline")
def run_hla_pipeline(self, job_id: str) -> dict:
    logger.info("[pipeline] Starting job %s", job_id)

    try:
        job = _get_job(job_id)

        # Stage 1: start EC2
        _update_job(job_id, status="running", stage="ec2_starting")
        logger.info("[pipeline] %s → ec2_starting", job_id)

        ec2 = get_ec2_backend()
        instance_id = ec2.spawn_instance(job["tier"])
        logger.info("[pipeline] %s instance spawned: %s", job_id, instance_id)

        # Stage 2: run HLA
        _update_job(job_id, instance_id=instance_id, stage="hla_running")
        logger.info("[pipeline] %s → hla_running", job_id)

        storage = get_storage_backend()
        file_path = storage.file_path(job["storage_key"])

        hla = get_hla_runner()
        result = hla.run(file_path, job["file_type"])
        logger.info("[pipeline] %s HLA done: %s", job_id, result)

        # Stage 3: done
        # psycopg2 doesn't auto-cast dicts to JSON; use the Json adapter
        from psycopg2.extras import Json
        _update_job(
            job_id,
            status="completed",
            stage="done",
            result=Json(result),
        )
        logger.info("[pipeline] %s → completed", job_id)

        # Clean up
        ec2.terminate_instance(instance_id)
        logger.info("[pipeline] %s instance terminated", job_id)

        return result

    except Exception as exc:
        logger.exception("[pipeline] %s failed: %s", job_id, exc)
        _update_job(job_id, status="failed", error=str(exc))
        raise
