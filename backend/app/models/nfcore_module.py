from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NfCoreModule(Base):
    __tablename__ = "nfcore_modules"

    id: Mapped[str] = mapped_column(String, primary_key=True)           # "samtools/sort"
    tool: Mapped[str] = mapped_column(String, nullable=False, index=True)
    subcommand: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    keywords: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=False, default="Other", index=True)
    inputs: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    outputs: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
