"""add storage_key_r2 and workflow_config to jobs

Revision ID: 0009
Revises: 0008
Create Date: 2026-02-26 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS storage_key_r2 VARCHAR")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS workflow_config JSON")


def downgrade() -> None:
    op.drop_column("jobs", "storage_key_r2")
    op.drop_column("jobs", "workflow_config")
