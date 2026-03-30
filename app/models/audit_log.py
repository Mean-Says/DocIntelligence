import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    client_id: Optional[str] = Field(default=None, index=True)  # None = tentativa sem auth
    ip_address: str
    method: str
    path: str
    status_code: int
    latency_ms: int
    user_agent: Optional[str] = Field(default=None)
    document_id: Optional[str] = Field(default=None)  # preenchido em /extract
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
