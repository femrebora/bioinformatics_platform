"""add stripe_session_id to jobs

Revision ID: 0008
Revises: 0007
Create Date: 2026-02-26 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS stripe_session_id VARCHAR")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_jobs_stripe_session_id ON jobs (stripe_session_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_jobs_stripe_session_id")
    op.drop_column("jobs", "stripe_session_id")
