from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SnakemakeWrapper(Base):
    __tablename__ = "snakemake_wrappers"

    id: Mapped[str] = mapped_column(String, primary_key=True)            # "bio/samtools/sort"
    tool: Mapped[str] = mapped_column(String, nullable=False, index=True)
    subcommand: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    authors: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    input_names: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    output_names: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=False, default="Other", index=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
