"""
Tipos SQLAlchemy que se adaptam ao dialeto.
JSONB no Postgres (queryável, indexável), JSON no SQLite (dev/testes).
"""
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator


class JSONBAdaptive(TypeDecorator):
    """Usa JSONB no Postgres, JSON em qualquer outro dialeto (SQLite para testes)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())
