"""
Endpoints de gestão da conta do cliente:
- POST /v1/account/rotate-key   — gera nova API key, invalida a anterior
- DELETE /v1/account            — exclui todos os dados (LGPD)
- GET /v1/account/usage         — uso do mês atual
"""
import hashlib
import secrets
import bcrypt
from datetime import datetime, timezone
from sqlmodel import select, delete

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.deps import SessionDep, ClientDep
from app.models.document import Document, DocumentStatus
from app.models.extraction import Extraction
from app.models.audit_log import AuditLog

router = APIRouter(tags=["account"])


class RotateKeyResponse(BaseModel):
    api_key: str
    message: str


class UsageResponse(BaseModel):
    month: str
    documents_processed: int
    documents_failed: int
    avg_confidence: float | None
    plan: str


@router.post("/rotate-key", response_model=RotateKeyResponse)
async def rotate_key(session: SessionDep, client: ClientDep):
    """Gera uma nova API key e invalida a anterior imediatamente."""
    new_key = f"di_sk_{secrets.token_hex(32)}"
    new_hash = bcrypt.hashpw(new_key.encode(), bcrypt.gensalt()).decode()
    new_lookup = hashlib.sha256(new_key.encode()).hexdigest()

    client.api_key_hash = new_hash
    client.api_key_lookup = new_lookup
    session.add(client)
    await session.commit()

    return RotateKeyResponse(
        api_key=new_key,
        message="Nova chave gerada. A chave anterior foi invalidada imediatamente. Guarde esta chave — ela não será exibida novamente.",
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(session: SessionDep, client: ClientDep):
    """
    LGPD: exclui todos os dados do cliente.
    Remove documentos, extrações, logs de auditoria e o próprio cliente.
    """
    client_id = client.id

    # Busca todos os document_ids do cliente
    doc_result = await session.exec(select(Document.id).where(Document.client_id == client_id))
    doc_ids = doc_result.all()

    if doc_ids:
        # Deleta extrações
        for doc_id in doc_ids:
            await session.exec(delete(Extraction).where(Extraction.document_id == doc_id))

        # Deleta documentos
        await session.exec(delete(Document).where(Document.client_id == client_id))

    # Deleta logs de auditoria
    await session.exec(delete(AuditLog).where(AuditLog.client_id == client_id))

    # Deleta o cliente
    await session.delete(client)
    await session.commit()


@router.get("/usage", response_model=UsageResponse)
async def get_usage(session: SessionDep, client: ClientDep):
    """Retorna uso do mês atual."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await session.exec(
        select(Document).where(
            Document.client_id == client.id,
            Document.created_at >= month_start,
        )
    )
    docs = result.all()

    processed = [d for d in docs if d.status == DocumentStatus.DONE]
    failed = [d for d in docs if d.status == DocumentStatus.FAILED]

    # Calcula confiança média dos processados
    avg_confidence = None
    if processed:
        doc_ids = [d.id for d in processed]
        ext_result = await session.exec(
            select(Extraction).where(Extraction.document_id.in_(doc_ids))
        )
        extractions = ext_result.all()
        if extractions:
            avg_confidence = round(
                sum(e.overall_confidence for e in extractions if e.overall_confidence) / len(extractions),
                3,
            )

    return UsageResponse(
        month=now.strftime("%Y-%m"),
        documents_processed=len(processed),
        documents_failed=len(failed),
        avg_confidence=avg_confidence,
        plan=client.plan,
    )
