"""add api_key_lookup to clients

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-30
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("api_key_lookup", sa.String(), nullable=True))
    # Preenche lookup para clientes existentes com hash vazio (força recriar API key)
    op.execute("UPDATE clients SET api_key_lookup = api_key_hash WHERE api_key_lookup IS NULL")
    op.alter_column("clients", "api_key_lookup", nullable=False)
    op.create_unique_constraint("uq_clients_api_key_lookup", "clients", ["api_key_lookup"])
    op.create_index("ix_clients_api_key_lookup", "clients", ["api_key_lookup"])


def downgrade() -> None:
    op.drop_index("ix_clients_api_key_lookup", "clients")
    op.drop_constraint("uq_clients_api_key_lookup", "clients")
    op.drop_column("clients", "api_key_lookup")
