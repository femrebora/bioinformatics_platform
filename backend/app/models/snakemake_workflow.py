from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, DateTime, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SnakemakeWorkflow(Base):
    __tablename__ = "snakemake_workflows"

    id: Mapped[str] = mapped_column(String, primary_key=True)            # "snakemake-workflows/dna-seq-gatk-variant-calling"
    name: Mapped[str] = mapped_column(String, nullable=False)            # "dna-seq-gatk-variant-calling"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topics: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    html_url: Mapped[str] = mapped_column(String, nullable=False, default="")
    stars: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
