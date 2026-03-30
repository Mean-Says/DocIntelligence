"""add audit_logs table

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-30
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("client_id", sa.String(), nullable=True, index=True),
        sa.Column("ip_address", sa.String(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("document_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
