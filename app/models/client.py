import uuid
from datetime import datetime
from sqlmodel import Field, SQLModel


class Client(SQLModel, table=True):
    __tablename__ = "clients"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True)
    api_key_hash: str = Field(unique=True)    # bcrypt hash — verificação de segurança
    api_key_lookup: str = Field(unique=True)  # sha256 do token — índice para lookup O(1)
    plan: str = Field(default="free")         # free | starter | pro
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
