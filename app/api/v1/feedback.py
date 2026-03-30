from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.deps import SessionDep, ClientDep
from app.models.document import Document, DocumentStatus
from app.models.extraction import Extraction
from app.models.feedback import Feedback

router = APIRouter()


class FeedbackRequest(BaseModel):
    document_id: str
    field: str
    correct_value: str


class FeedbackResponse(BaseModel):
    accepted: bool
    triggered_relearn: bool


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(body: FeedbackRequest, session: SessionDep, client: ClientDep):
    # Valida que o documento pertence ao cliente
    doc = await session.get(Document, body.document_id)
    if not doc or doc.client_id != client.id:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    if doc.status != DocumentStatus.DONE:
        raise HTTPException(status_code=400, detail="Documento ainda não processado")

    # Busca extração para comparar valores
    ext_result = await session.exec(
        select(Extraction).where(Extraction.document_id == body.document_id)
    )
    extraction = ext_result.first()
    extracted_value = extraction.fields.get(body.field, "") if extraction else ""

    was_correct = extracted_value == body.correct_value

    # Dispara relearn se estava errado e foi processado por AI (nível 3 ou 4)
    triggered_relearn = False
    if not was_correct and extraction and extraction.level_used >= 3:
        from arq.connections import create_pool, RedisSettings
        from app.config import settings
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis.enqueue_job("run_learning_loop", body.document_id)
        await redis.close()
        triggered_relearn = True

    feedback = Feedback(
        document_id=body.document_id,
        client_id=client.id,
        field_name=body.field,
        extraction_value=extracted_value,
        submitted_value=body.correct_value,
        was_correct=was_correct,
        triggered_relearn=triggered_relearn,
        created_at=datetime.utcnow(),
    )
    session.add(feedback)
    await session.commit()

    return FeedbackResponse(accepted=True, triggered_relearn=triggered_relearn)
