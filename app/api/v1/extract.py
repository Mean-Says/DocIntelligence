"""
POST /v1/extract  — recebe documento, enfileira extração
GET  /v1/jobs/{job_id} — polling do resultado
"""
import uuid
import tempfile
from pathlib import Path
from datetime import datetime

from arq import ArqRedis
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlmodel import select

from fastapi import Request
from app.config import settings
from app.db import AsyncSessionLocal
from app.deps import SessionDep, ClientDep
from app.models.document import Document, DocumentStatus
from app.models.extraction import Extraction
from app.storage import r2
from app.utils.mime import is_allowed as mime_is_allowed

router = APIRouter()


class ExtractResponse(BaseModel):
    job_id: str
    document_id: str
    status: str
    status_url: str


class JobResult(BaseModel):
    job_id: str
    status: str
    document_id: str | None = None
    doc_type: str | None = None
    doc_type_confidence: float | None = None
    processing_level: int | None = None
    data: dict | None = None
    confidence: dict | None = None
    overall_confidence: float | None = None
    processing_ms: int | None = None
    error: str | None = None


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def extract(
    request: Request,
    session: SessionDep,
    client: ClientDep,
    file: UploadFile = File(...),
    doc_type: str | None = Form(None),
):
    # Registra client_id no state para o middleware de auditoria
    request.state.client_id = client.id

    # Valida tamanho
    content = await file.read()
    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo maior que {settings.max_file_size_mb}MB",
        )

    # Valida mime type real (inspeciona magic bytes — não confia no header)
    allowed, detected_mime = mime_is_allowed(content)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de arquivo não suportado.",
        )

    # Salva temporariamente e faz upload para R2
    suffix = Path(file.filename or "doc.pdf").suffix
    doc_id = str(uuid.uuid4())
    storage_key = f"clients/{client.id}/{doc_id}{suffix}"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    await r2.upload(tmp_path, storage_key)
    Path(tmp_path).unlink(missing_ok=True)

    # Cria registro no banco
    doc = Document(
        id=doc_id,
        client_id=client.id,
        file_name=file.filename or f"document{suffix}",
        storage_key=storage_key,
        doc_type=doc_type,
        status=DocumentStatus.PENDING,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(doc)
    request.state.document_id = doc_id  # para o middleware de auditoria

    # Enfileira job ARQ (processa inline em dev quando Redis não está disponível)
    from arq.connections import create_pool, RedisSettings
    from app.config import settings as cfg
    try:
        redis = await create_pool(RedisSettings.from_dsn(cfg.redis_url))
        job = await redis.enqueue_job("process_document", doc_id)
        await redis.close()
    except Exception:
        # Dev sem Redis: processa inline e retorna 200 direto
        from app.workers.tasks import process_document
        import fakeredis.aioredis

        fake = fakeredis.aioredis.FakeRedis()
        ctx = {"redis": fake}

        class _FakeJob:
            job_id = f"dev-job-{doc_id}"

        job = _FakeJob()
        doc.job_id = job.job_id
        await session.commit()

        # Processa sincronamente — retorna quando terminar
        await process_document(ctx, doc_id)

        # Retorna 200 com resultado direto
        from sqlmodel import select
        from app.models.extraction import Extraction
        ext_res = await session.exec(select(Extraction).where(Extraction.document_id == doc_id))
        extraction = ext_res.first()
        doc_refreshed = await session.get(Document, doc_id)

        if extraction and doc_refreshed:
            return JobResult(
                job_id=job.job_id,
                status=doc_refreshed.status,
                document_id=doc_id,
                doc_type=doc_refreshed.doc_type,
                doc_type_confidence=doc_refreshed.doc_type_confidence,
                processing_level=extraction.level_used,
                data=extraction.fields,
                confidence=extraction.confidence_scores,
                overall_confidence=extraction.overall_confidence,
                processing_ms=extraction.processing_ms,
            )

        return ExtractResponse(
            job_id=job.job_id,
            document_id=doc_id,
            status="done",
            status_url=f"/v1/extract/jobs/{job.job_id}",
        )

    doc.job_id = job.job_id
    await session.commit()

    return ExtractResponse(
        job_id=job.job_id,
        document_id=doc_id,
        status="pending",
        status_url=f"/v1/jobs/{job.job_id}",
    )


@router.get("/jobs/{job_id}", response_model=JobResult)
async def get_job(job_id: str, session: SessionDep, client: ClientDep):
    # Busca documento pelo job_id
    result = await session.exec(
        select(Document).where(
            Document.job_id == job_id,
            Document.client_id == client.id,
        )
    )
    doc = result.first()

    if not doc:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if doc.status == DocumentStatus.FAILED:
        return JobResult(job_id=job_id, status="failed", document_id=doc.id, error=doc.error_message)

    if doc.status != DocumentStatus.DONE:
        return JobResult(job_id=job_id, status=doc.status.value, document_id=doc.id)

    # Busca extração
    ext_result = await session.exec(
        select(Extraction).where(Extraction.document_id == doc.id)
    )
    extraction = ext_result.first()

    if not extraction:
        return JobResult(job_id=job_id, status="processing", document_id=doc.id)

    return JobResult(
        job_id=job_id,
        status="done",
        document_id=doc.id,
        doc_type=doc.doc_type,
        doc_type_confidence=doc.doc_type_confidence,
        processing_level=extraction.level_used,
        data=extraction.fields,
        confidence=extraction.confidence_scores,
        overall_confidence=extraction.overall_confidence,
        processing_ms=extraction.processing_ms,
    )
