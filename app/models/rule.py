import uuid
from datetime import datetime
from enum import StrEnum
from typing import Optional
from sqlmodel import Field, SQLModel


class RuleScope(StrEnum):
    GLOBAL = "global"   # compartilhada entre todos os clientes
    CLIENT = "client"   # isolada por cliente


class RuleStatus(StrEnum):
    ACTIVE = "active"
    PENDING_REVIEW = "pending_review"  # aguardando acúmulo de N docs
    DISABLED = "disabled"


class RuleOrigin(StrEnum):
    HANDCRAFTED = "handcrafted"  # escrita manualmente (seed)
    AI_GENERATED = "ai_generated"


class Rule(SQLModel, table=True):
    __tablename__ = "rules"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    doc_type: str = Field(index=True)    # nfe, curriculo, conta_luz, contrato
    field_name: str = Field(index=True)  # campo que essa regra extrai

    scope: RuleScope = Field(default=RuleScope.GLOBAL)
    client_id: Optional[str] = Field(default=None, foreign_key="clients.id", index=True)

    pattern: str           # regex string
    capture_group: int = Field(default=1)
    # normalizer: função de normalização a aplicar no valor capturado
    # valores: strip | digits_only | date_iso | currency_brl | none
    normalizer: str = Field(default="strip")

    # Prioridade: menor número = tentado primeiro dentro do mesmo doc_type+field_name
    # Regras de cliente recebem priority=0 para sobrescrever globais
    priority: int = Field(default=100)

    # Confiança atribuída quando a regra dispara com sucesso
    confidence_baseline: float = Field(default=0.85)

    # Métricas de uso — atualizadas em batch
    hit_count: int = Field(default=0)
    fail_count: int = Field(default=0)

    status: RuleStatus = Field(default=RuleStatus.ACTIVE, index=True)
    origin: RuleOrigin = Field(default=RuleOrigin.HANDCRAFTED)

    # Qual documento gerou essa regra (se AI_GENERATED)
    generated_from_doc_id: Optional[str] = Field(default=None, foreign_key="documents.id")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ValidationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    QUEUED_HUMAN = "queued_human"


class RuleCandidate(SQLModel, table=True):
    """
    Regra gerada pelo AI que ainda não foi promovida para a tabela rules.
    Fica aqui enquanto acumula validações ou aguarda revisão humana.
    """
    __tablename__ = "rule_candidates"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    document_id: str = Field(foreign_key="documents.id", index=True)
    doc_type: str
    field_name: str

    pattern: str
    capture_group: int = Field(default=1)
    normalizer: str = Field(default="strip")

    generator_model: str
    generator_output: Optional[str] = Field(default=None)  # raw output do LLM

    validation_status: ValidationStatus = Field(default=ValidationStatus.PENDING)
    validation_model: Optional[str] = Field(default=None)
    validation_confidence: Optional[float] = Field(default=None)

    # Quantos documentos diferentes essa candidata já foi validada com sucesso
    validation_count: int = Field(default=1)

    # Preenchido quando promovida para rules
    promoted_rule_id: Optional[str] = Field(default=None, foreign_key="rules.id")

    created_at: datetime = Field(default_factory=datetime.utcnow)
