"""add job_name to jobs

Revision ID: 0010
Revises: 0009
Create Date: 2026-02-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("job_name", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "job_name")
