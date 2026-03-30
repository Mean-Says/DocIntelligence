import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel
from sqlalchemy import Column
from app.utils.db_types import JSONBAdaptive


class Extraction(SQLModel, table=True):
    __tablename__ = "extractions"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    document_id: str = Field(foreign_key="documents.id", unique=True, index=True)

    # JSONB no Postgres (queryável), JSON no SQLite (dev/testes)
    fields: dict = Field(default_factory=dict, sa_column=Column(JSONBAdaptive, nullable=False))
    confidence_scores: dict = Field(default_factory=dict, sa_column=Column(JSONBAdaptive, nullable=False))
    overall_confidence: float = Field(default=0.0)

    level_used: int  # 1-4
    model_used: Optional[str] = Field(default=None)  # nome do modelo AI se usado
    raw_text: Optional[str] = Field(default=None)    # texto completo extraído

    processing_ms: Optional[int] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
