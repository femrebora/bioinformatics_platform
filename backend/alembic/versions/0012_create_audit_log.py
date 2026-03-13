"""create audit_log table

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id",            sa.String(), nullable=False, primary_key=True),
        sa.Column("user_id",       sa.String(), nullable=True),
        sa.Column("action",        sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_id",   sa.String(), nullable=True),
        sa.Column("ip_address",    sa.String(), nullable=True),
        sa.Column("user_agent",    sa.String(), nullable=True),
        sa.Column("meta",          sa.JSON(),   nullable=True),
        sa.Column("created_at",    sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_log_user_id",   "audit_log", ["user_id"])
    op.create_index("ix_audit_log_action",    "audit_log", ["action"])
    op.create_index("ix_audit_log_created_at","audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_action",     table_name="audit_log")
    op.drop_index("ix_audit_log_user_id",    table_name="audit_log")
    op.drop_table("audit_log")
