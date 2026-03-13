"""
Audit logging service.

Non-blocking fire-and-forget: each call opens its own short-lived DB session
so it never delays or rolls back the caller's transaction.
All exceptions are silently swallowed — audit loss is preferable to request failure.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


async def log_audit(
    action: str,
    *,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Append one row to audit_log.

    Call with ``await`` — completes quickly (single INSERT) and never raises.

    Actions (not exhaustive):
      auth.register, auth.login, auth.delete_account
      job.create, job.cancel, job.retry, job.download
    """
    try:
        from app.database import AsyncSessionLocal
        from app.models.audit_log import AuditLog

        entry = AuditLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            meta=meta,
            created_at=datetime.now(timezone.utc),
        )
        async with AsyncSessionLocal() as db:
            db.add(entry)
            await db.commit()
    except Exception as exc:
        logger.debug("audit log write failed (non-fatal): %s", exc)


def _ip(request: Any) -> str | None:
    """Extract client IP from a FastAPI Request, honouring X-Forwarded-For."""
    try:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[0].strip()
        return request.client.host if request.client else None
    except Exception:
        return None


def _ua(request: Any) -> str | None:
    """Extract User-Agent header (truncated to 256 chars)."""
    try:
        ua = request.headers.get("user-agent", "")
        return ua[:256] or None
    except Exception:
        return None
