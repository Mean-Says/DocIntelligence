import uuid
from datetime import datetime
from enum import StrEnum
from typing import Optional
from sqlmodel import Field, SQLModel


class FileType(StrEnum):
    PDF_BINARY = "pdf_binary"    # PDF com texto extraível
    PDF_SCANNED = "pdf_scanned"  # PDF com imagens (OCR necessário)
    IMAGE = "image"              # JPG, PNG, TIFF


class DocumentType(StrEnum):
    NFE = "nfe"
    CONTA_LUZ = "conta_luz"
    CURRICULO = "curriculo"
    CONTRATO = "contrato"
    UNKNOWN = "unknown"


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"  # confiança baixa, fila humana


class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    client_id: str = Field(foreign_key="clients.id", index=True)

    file_name: str
    file_type: Optional[FileType] = Field(default=None)
    storage_key: str  # chave no R2, não URL pública

    doc_type: Optional[DocumentType] = Field(default=None, index=True)
    doc_type_confidence: Optional[float] = Field(default=None)

    status: DocumentStatus = Field(default=DocumentStatus.PENDING, index=True)
    processing_level: Optional[int] = Field(default=None)  # 1-4
    job_id: Optional[str] = Field(default=None)  # ARQ job ID para polling

    error_message: Optional[str] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
