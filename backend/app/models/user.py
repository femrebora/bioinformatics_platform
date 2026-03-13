from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Valid roles: "user" (default), "clinician", "admin"
ROLES = {"user", "clinician", "admin"}


class User(Base):
    __tablename__ = "users"

    id:              Mapped[str]      = mapped_column(String, primary_key=True)
    email:           Mapped[str]      = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str]      = mapped_column(String, nullable=False)
    is_active:       Mapped[bool]     = mapped_column(Boolean, default=True, nullable=False)
    role:            Mapped[str]      = mapped_column(String, nullable=False, default="user", server_default="user")
    created_at:      Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
