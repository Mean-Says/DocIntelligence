"""
ARQ tasks — rodam em worker separado do processo da API.
"""
import tempfile
import uuid
from datetime import datetime

from arq import ArqRedis
from sqlmodel import select

from app.config import settings
from app.db import AsyncSessionLocal
from app.models.document import Document, DocumentStatus
from app.models.extraction import Extraction
from app.models.rule import Rule, RuleCandidate, RuleScope, RuleStatus, RuleOrigin, ValidationStatus
from app.pipeline import orchestrator
from app.storage import r2


async def process_document(ctx: dict, document_id: str) -> dict:
    """
    Job principal: executa o pipeline de extração para um documento.
    Chamado pelo worker ARQ.
    """
    redis: ArqRedis = ctx["redis"]

    async with AsyncSessionLocal() as session:
        # Carrega documento
        doc = await session.get(Document, document_id)
        if not doc:
            return {"error": f"document {document_id} not found"}

        # Atualiza status
        doc.status = DocumentStatus.PROCESSING
        doc.updated_at = datetime.utcnow()
        await session.commit()

        try:
            # Faz download do arquivo para temp dir
            with tempfile.NamedTemporaryFile(suffix=_suffix(doc.file_name), delete=False) as tmp:
                tmp_path = tmp.name

            await r2.download(doc.storage_key, tmp_path)

            # Executa pipeline
            result, doc_type, doc_type_confidence = await orchestrator.run(
                file_path=tmp_path,
                client_id=doc.client_id,
                doc_type_hint=doc.doc_type,
                session=session,
                redis=redis,
            )

            # Atualiza documento — file_type já foi detectado pelo orchestrator via detector.py
            from app.pipeline.detector import detect_file_type
            doc.file_type, _ = detect_file_type(tmp_path)
            doc.doc_type = doc_type
            doc.doc_type_confidence = doc_type_confidence
            doc.status = DocumentStatus.DONE
            doc.processing_level = result.level_used
            doc.updated_at = datetime.utcnow()

            # Salva extração
            extraction = Extraction(
                document_id=document_id,
                fields=result.fields,
                confidence_scores=result.confidence_scores,
                overall_confidence=result.overall_confidence,
                level_used=result.level_used,
                model_used=result.model_used,
                raw_text=result.raw_text,
                processing_ms=result.processing_ms,
            )
            session.add(extraction)
            await session.commit()

            # Dispara learning loop se necessário (não bloqueia a resposta)
            if result.needs_learning_loop:
                redis = ctx.get("redis")
                try:
                    await redis.enqueue_job("run_learning_loop", document_id)
                except (AttributeError, Exception):
                    # Dev/fakeredis: roda inline
                    await run_learning_loop(ctx, document_id)

            return {
                "document_id": document_id,
                "level_used": result.level_used,
                "overall_confidence": result.overall_confidence,
            }

        except Exception as e:
            doc.status = DocumentStatus.FAILED
            doc.error_message = str(e)
            doc.updated_at = datetime.utcnow()
            await session.commit()
            raise


async def run_learning_loop(ctx: dict, document_id: str) -> dict:
    """
    Para cada campo extraído por AI:
    1. Claude gera regex candidata
    2. Groq valida a regex no mesmo texto
    3. Salva RuleCandidate e promove para Rule se confiança alta
    """
    from app.rule_engine.generator import generate_rule_candidate
    from app.rule_engine.validator import validate_rule_candidate
    from app.rule_engine.loader import invalidate_cache

    promoted = 0
    queued = 0
    rejected = 0

    async with AsyncSessionLocal() as session:
        doc = await session.get(Document, document_id)
        if not doc:
            return {"error": "document not found"}

        ext_result = await session.exec(
            select(Extraction).where(Extraction.document_id == document_id)
        )
        extraction = ext_result.first()
        if not extraction or not extraction.raw_text:
            return {"document_id": document_id, "status": "skipped_no_raw_text"}

        doc_type = doc.doc_type
        raw_text = extraction.raw_text

        for field_name, value in extraction.fields.items():
            if not value:
                continue

            # Verifica se já existe regra ativa para esse campo
            existing = await session.exec(
                select(Rule).where(
                    Rule.doc_type == doc_type,
                    Rule.field_name == field_name,
                    Rule.scope == RuleScope.GLOBAL,
                    Rule.status == RuleStatus.ACTIVE,
                )
            )
            if existing.first():
                continue  # já tem regra — não regera

            # 1. Gera regex candidata via Claude
            candidate_data = await generate_rule_candidate(
                doc_type=doc_type,
                field_name=field_name,
                value=value,
                raw_text=raw_text,
            )
            if not candidate_data:
                rejected += 1
                continue

            # 2. Valida via Groq
            validation = await validate_rule_candidate(
                pattern=candidate_data["pattern"],
                capture_group=candidate_data.get("capture_group", 1),
                normalizer=candidate_data.get("normalizer", "strip"),
                expected_value=value,
                raw_text=raw_text,
            )

            confidence = validation.get("confidence", 0.0)

            # Determina status da candidata
            if confidence >= settings.learning_loop_auto_promote and validation.get("structural_ok", True):
                v_status = ValidationStatus.APPROVED
            elif confidence >= settings.learning_loop_queue_human:
                v_status = ValidationStatus.PENDING   # acumula N docs antes de promover
            else:
                v_status = ValidationStatus.REJECTED
                rejected += 1

            # Salva RuleCandidate
            candidate = RuleCandidate(
                id=str(uuid.uuid4()),
                document_id=document_id,
                doc_type=doc_type,
                field_name=field_name,
                pattern=candidate_data["pattern"],
                capture_group=candidate_data.get("capture_group", 1),
                normalizer=candidate_data.get("normalizer", "strip"),
                generator_model=settings.extractor_model,
                generator_output=candidate_data.get("explanation"),
                validation_status=v_status,
                validation_model=settings.validator_model,
                validation_confidence=confidence,
                validation_count=1,
                created_at=datetime.utcnow(),
            )
            session.add(candidate)

            # 3. Promove diretamente se aprovada
            if v_status == ValidationStatus.APPROVED:
                rule = Rule(
                    id=str(uuid.uuid4()),
                    doc_type=doc_type,
                    field_name=field_name,
                    scope=RuleScope.GLOBAL,
                    pattern=candidate_data["pattern"],
                    capture_group=candidate_data.get("capture_group", 1),
                    normalizer=candidate_data.get("normalizer", "strip"),
                    priority=50,  # prioridade menor que handcrafted (10), maior que padrão (100)
                    confidence_baseline=min(confidence, 0.92),
                    status=RuleStatus.ACTIVE,
                    origin=RuleOrigin.AI_GENERATED,
                    generated_from_doc_id=document_id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(rule)
                candidate.promoted_rule_id = rule.id
                promoted += 1

                # Invalida cache Redis para esse doc_type
                if ctx.get("redis"):
                    await invalidate_cache(doc_type, doc.client_id, ctx["redis"])

            elif v_status == ValidationStatus.PENDING:
                # Verifica se há outras candidatas iguais acumuladas
                similar = await session.exec(
                    select(RuleCandidate).where(
                        RuleCandidate.doc_type == doc_type,
                        RuleCandidate.field_name == field_name,
                        RuleCandidate.pattern == candidate_data["pattern"],
                        RuleCandidate.validation_status == ValidationStatus.PENDING,
                        RuleCandidate.promoted_rule_id == None,
                    )
                )
                similar_list = similar.all()

                if len(similar_list) >= settings.learning_loop_accumulate_n - 1:
                    # Acumulou N docs — promove
                    rule = Rule(
                        id=str(uuid.uuid4()),
                        doc_type=doc_type,
                        field_name=field_name,
                        scope=RuleScope.GLOBAL,
                        pattern=candidate_data["pattern"],
                        capture_group=candidate_data.get("capture_group", 1),
                        normalizer=candidate_data.get("normalizer", "strip"),
                        priority=60,
                        confidence_baseline=min(confidence, 0.85),
                        status=RuleStatus.ACTIVE,
                        origin=RuleOrigin.AI_GENERATED,
                        generated_from_doc_id=document_id,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    session.add(rule)
                    for s in similar_list:
                        s.promoted_rule_id = rule.id
                        s.validation_status = ValidationStatus.APPROVED
                    candidate.promoted_rule_id = rule.id
                    promoted += 1

                    if ctx.get("redis"):
                        await invalidate_cache(doc_type, doc.client_id, ctx["redis"])
                else:
                    queued += 1

        await session.commit()

    return {
        "document_id": document_id,
        "promoted": promoted,
        "queued_for_accumulation": queued,
        "rejected": rejected,
    }


def _suffix(file_name: str) -> str:
    from pathlib import Path
    return Path(file_name).suffix or ".pdf"
