"""create snakemake tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-02-24 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use IF NOT EXISTS — tables may already exist if created by SQLAlchemy metadata
    # before this migration first ran (startup create_all in main.py).
    op.execute("""
        CREATE TABLE IF NOT EXISTS snakemake_wrappers (
            id          VARCHAR PRIMARY KEY,
            tool        VARCHAR NOT NULL,
            subcommand  VARCHAR,
            name        VARCHAR,
            description TEXT,
            authors     JSON,
            input_names JSON,
            output_names JSON,
            category    VARCHAR NOT NULL DEFAULT 'Other',
            fetched_at  TIMESTAMPTZ
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_snakemake_wrappers_tool     ON snakemake_wrappers (tool)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_snakemake_wrappers_category ON snakemake_wrappers (category)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS snakemake_workflows (
            id          VARCHAR PRIMARY KEY,
            name        VARCHAR NOT NULL,
            description TEXT,
            topics      JSON,
            html_url    VARCHAR NOT NULL DEFAULT '',
            stars       INTEGER NOT NULL DEFAULT 0,
            fetched_at  TIMESTAMPTZ
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_snakemake_workflows_stars ON snakemake_workflows (stars)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_snakemake_workflows_stars")
    op.drop_table("snakemake_workflows")
    op.execute("DROP INDEX IF EXISTS ix_snakemake_wrappers_category")
    op.execute("DROP INDEX IF EXISTS ix_snakemake_wrappers_tool")
    op.drop_table("snakemake_wrappers")
