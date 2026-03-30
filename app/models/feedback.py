import uuid
from datetime import datetime
from sqlmodel import Field, SQLModel


class Feedback(SQLModel, table=True):
    __tablename__ = "feedbacks"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    document_id: str = Field(foreign_key="documents.id", index=True)
    client_id: str = Field(foreign_key="clients.id", index=True)

    field_name: str
    extraction_value: str   # o que o sistema extraiu
    submitted_value: str    # o que o usuário diz ser correto
    was_correct: bool       # sistema acertou?

    # Se esse feedback disparou um novo ciclo de aprendizado
    triggered_relearn: bool = Field(default=False)

    created_at: datetime = Field(default_factory=datetime.utcnow)
