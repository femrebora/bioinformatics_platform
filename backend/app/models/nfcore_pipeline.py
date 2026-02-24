from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NfCorePipeline(Base):
    __tablename__ = "nfcore_pipelines"

    id: Mapped[str] = mapped_column(String, primary_key=True)           # "rnaseq"
    full_name: Mapped[str] = mapped_column(String, nullable=False)      # "nf-core/rnaseq"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topics: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    html_url: Mapped[str] = mapped_column(String, nullable=False, default="")
    stars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_formats: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
