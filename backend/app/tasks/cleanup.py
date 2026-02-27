"""Background cleanup tasks (GDPR erasure, S3 key deletion)."""
import logging
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.cleanup.delete_storage_keys")
def delete_storage_keys(storage_keys: list[str]) -> dict:
    """Delete a list of storage keys from the configured storage backend.

    Called after account deletion to fulfil GDPR right-to-erasure.
    Failures are logged but do not raise — the user row is already gone.
    """
    from app.services.storage.base import get_storage_backend
    storage = get_storage_backend()
    deleted, failed = 0, 0

    for key in storage_keys:
        try:
            storage.delete(key)
            deleted += 1
            logger.info("[cleanup] deleted storage key: %s", key)
        except Exception as exc:
            failed += 1
            logger.warning("[cleanup] failed to delete %s: %s", key, exc)

    logger.info("[cleanup] storage cleanup done — deleted=%d failed=%d", deleted, failed)
    return {"deleted": deleted, "failed": failed}
