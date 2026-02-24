"""add pipeline_id to jobs

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-24 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use IF NOT EXISTS — column may already exist in databases created before
    # this migration was written.
    op.execute(
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS pipeline_id VARCHAR"
    )


def downgrade() -> None:
    op.drop_column("jobs", "pipeline_id")
