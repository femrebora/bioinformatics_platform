"""create nfcore tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    existing = inspect(conn).get_table_names()

    if "nfcore_pipelines" not in existing:
        op.create_table(
            "nfcore_pipelines",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("full_name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("topics", sa.JSON(), nullable=True),
            sa.Column("html_url", sa.String(), nullable=False, server_default=""),
            sa.Column("stars", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True),
            sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    if "nfcore_modules" not in existing:
        op.create_table(
            "nfcore_modules",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("tool", sa.String(), nullable=False),
            sa.Column("subcommand", sa.String(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("keywords", sa.JSON(), nullable=True),
            sa.Column("category", sa.String(), nullable=False, server_default="Other"),
            sa.Column("inputs", sa.JSON(), nullable=True),
            sa.Column("outputs", sa.JSON(), nullable=True),
            sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_nfcore_modules_tool", "nfcore_modules", ["tool"])
        op.create_index("ix_nfcore_modules_category", "nfcore_modules", ["category"])


def downgrade() -> None:
    op.drop_index("ix_nfcore_modules_category", table_name="nfcore_modules")
    op.drop_index("ix_nfcore_modules_tool", table_name="nfcore_modules")
    op.drop_table("nfcore_modules")
    op.drop_table("nfcore_pipelines")
