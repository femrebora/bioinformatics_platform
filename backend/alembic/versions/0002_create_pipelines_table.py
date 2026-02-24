"""create pipelines table

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pipelines",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("graph", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pipelines_name", "pipelines", ["name"])

    op.add_column("jobs", sa.Column("pipeline_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "pipeline_id")
    op.drop_index("ix_pipelines_name", table_name="pipelines")
    op.drop_table("pipelines")
