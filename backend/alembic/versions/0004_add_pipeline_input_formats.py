"""add input_formats to nfcore_pipelines

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {c["name"] for c in inspect(conn).get_columns("nfcore_pipelines")}
    if "input_formats" not in cols:
        op.add_column(
            "nfcore_pipelines",
            sa.Column("input_formats", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("nfcore_pipelines", "input_formats")
