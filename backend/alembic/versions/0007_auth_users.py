"""create users table and add user_id to jobs/pipelines

Revision ID: 0007
Revises: 0006
Create Date: 2026-02-25 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id VARCHAR PRIMARY KEY,
            email VARCHAR NOT NULL UNIQUE,
            hashed_password VARCHAR NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"
    )
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS user_id VARCHAR")
    op.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS user_id VARCHAR")


def downgrade() -> None:
    op.drop_column("pipelines", "user_id")
    op.drop_column("jobs", "user_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
