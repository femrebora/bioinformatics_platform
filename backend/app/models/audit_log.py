from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    """Append-only audit trail for security and KVKK compliance.

    Every significant user action (login, job creation, data export, etc.)
    is recorded here.  Rows are never updated or deleted — this is a log.
    """
    __tablename__ = "audit_log"

    id:            Mapped[str]            = mapped_column(String, primary_key=True)
    user_id:       Mapped[str | None]     = mapped_column(String, nullable=True, index=True)
    action:        Mapped[str]            = mapped_column(String, nullable=False, index=True)
    resource_type: Mapped[str | None]     = mapped_column(String, nullable=True)
    resource_id:   Mapped[str | None]     = mapped_column(String, nullable=True)
    ip_address:    Mapped[str | None]     = mapped_column(String, nullable=True)
    user_agent:    Mapped[str | None]     = mapped_column(String, nullable=True)
    meta:          Mapped[Any | None]     = mapped_column(JSON, nullable=True)
    created_at:    Mapped[datetime]       = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
