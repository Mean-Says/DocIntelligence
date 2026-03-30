"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-29
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("api_key_hash", sa.String(), nullable=False, unique=True),
        sa.Column("plan", sa.String(), nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_clients_name", "clients", ["name"])

    op.create_table(
        "documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("client_id", sa.String(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("file_type", sa.String(), nullable=True),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("doc_type", sa.String(), nullable=True),
        sa.Column("doc_type_confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("processing_level", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_documents_client_id", "documents", ["client_id"])
    op.create_index("ix_documents_doc_type", "documents", ["doc_type"])
    op.create_index("ix_documents_status", "documents", ["status"])

    op.create_table(
        "extractions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_id", sa.String(), sa.ForeignKey("documents.id"), nullable=False, unique=True),
        sa.Column("fields", JSONB(), nullable=False, server_default="{}"),
        sa.Column("confidence_scores", JSONB(), nullable=False, server_default="{}"),
        sa.Column("overall_confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("level_used", sa.Integer(), nullable=False),
        sa.Column("model_used", sa.String(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("processing_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_extractions_document_id", "extractions", ["document_id"])

    op.create_table(
        "rules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("doc_type", sa.String(), nullable=False),
        sa.Column("field_name", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False, server_default="global"),
        sa.Column("client_id", sa.String(), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("capture_group", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("normalizer", sa.String(), nullable=False, server_default="strip"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("confidence_baseline", sa.Float(), nullable=False, server_default="0.85"),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("origin", sa.String(), nullable=False, server_default="handcrafted"),
        sa.Column("generated_from_doc_id", sa.String(), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_rules_doc_type", "rules", ["doc_type"])
    op.create_index("ix_rules_field_name", "rules", ["field_name"])
    op.create_index("ix_rules_status", "rules", ["status"])
    op.create_index("ix_rules_client_id", "rules", ["client_id"])

    op.create_table(
        "rule_candidates",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_id", sa.String(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("doc_type", sa.String(), nullable=False),
        sa.Column("field_name", sa.String(), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("capture_group", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("normalizer", sa.String(), nullable=False, server_default="strip"),
        sa.Column("generator_model", sa.String(), nullable=False),
        sa.Column("generator_output", sa.Text(), nullable=True),
        sa.Column("validation_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("validation_model", sa.String(), nullable=True),
        sa.Column("validation_confidence", sa.Float(), nullable=True),
        sa.Column("validation_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("promoted_rule_id", sa.String(), sa.ForeignKey("rules.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_rule_candidates_document_id", "rule_candidates", ["document_id"])

    op.create_table(
        "feedbacks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_id", sa.String(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("client_id", sa.String(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("field_name", sa.String(), nullable=False),
        sa.Column("extraction_value", sa.String(), nullable=False),
        sa.Column("submitted_value", sa.String(), nullable=False),
        sa.Column("was_correct", sa.Boolean(), nullable=False),
        sa.Column("triggered_relearn", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_feedbacks_document_id", "feedbacks", ["document_id"])
    op.create_index("ix_feedbacks_client_id", "feedbacks", ["client_id"])


def downgrade() -> None:
    op.drop_table("feedbacks")
    op.drop_table("rule_candidates")
    op.drop_table("rules")
    op.drop_table("extractions")
    op.drop_table("documents")
    op.drop_table("clients")
