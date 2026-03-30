"""
Orquestrador do pipeline de extração.
Decide qual nível ativar baseado nos thresholds de confiança.
"""
import time
from dataclasses import dataclass
from typing import Optional

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import DocumentType, FileType
from app.pipeline import detector
from app.pipeline.levels import level1_binary
from app.rule_engine import loader, matcher
from app.utils.confidence import compute_overall_confidence, missing_required_fields


@dataclass
class ExtractionResult:
    fields: dict[str, str]
    confidence_scores: dict[str, float]
    overall_confidence: float
    level_used: int
    model_used: Optional[str]
    raw_text: str
    processing_ms: int
    needs_learning_loop: bool  # True se usou AI (nível 3 ou 4)


async def run(
    file_path: str,
    client_id: str,
    doc_type_hint: Optional[str],
    session: AsyncSession,
    redis: Redis,
) -> tuple[ExtractionResult, DocumentType, float]:
    """
    Executa o pipeline completo.
    Retorna (ExtractionResult, doc_type detectado, doc_type_confidence).
    """
    start = time.monotonic()

    # ── Detecção ─────────────────────────────────────────────────────────────
    file_type, raw_text = detector.detect_file_type(file_path)

    if doc_type_hint:
        doc_type = DocumentType(doc_type_hint)
        doc_type_confidence = 1.0
    else:
        doc_type, doc_type_confidence = detector.detect_doc_type(raw_text)

    # ── Nível 1: padrões universais em PDF binário ────────────────────────────
    fields: dict[str, str] = {}
    confidence: dict[str, float] = {}

    if file_type == FileType.PDF_BINARY and raw_text:
        fields, confidence = level1_binary.extract(raw_text)
        overall = compute_overall_confidence(fields, confidence, doc_type.value)

        if overall >= settings.threshold_l1:
            return _result(fields, confidence, overall, 1, None, raw_text, start, False), doc_type, doc_type_confidence

    # ── Nível 2: rule engine ──────────────────────────────────────────────────
    if doc_type != DocumentType.UNKNOWN:
        rules = await loader.load_rules(doc_type.value, client_id, session, redis)
        if rules:
            fields, confidence = matcher.match(raw_text, rules, fields, confidence)
            overall = compute_overall_confidence(fields, confidence, doc_type.value)

            if overall >= settings.threshold_l2:
                return _result(fields, confidence, overall, 2, None, raw_text, start, False), doc_type, doc_type_confidence

    # ── OCR (se necessário) ───────────────────────────────────────────────────
    if file_type in (FileType.PDF_SCANNED, FileType.IMAGE):
        from app.utils.ocr import extract_text_from_file
        raw_text = await extract_text_from_file(file_path)

        # Re-roda rule engine no texto OCR
        if doc_type != DocumentType.UNKNOWN and rules:
            fields, confidence = matcher.match(raw_text, rules, fields, confidence)
            overall = compute_overall_confidence(fields, confidence, doc_type.value)
            if overall >= settings.threshold_l2:
                return _result(fields, confidence, overall, 2, None, raw_text, start, False), doc_type, doc_type_confidence

    # ── Nível 3: SLM via Groq ────────────────────────────────────────────────
    from app.pipeline.levels.level3_slm import extract as slm_extract
    slm_fields, slm_confidence, slm_model = await slm_extract(
        raw_text, doc_type.value, fields, confidence
    )
    fields, confidence = _merge(fields, confidence, slm_fields, slm_confidence)
    overall = compute_overall_confidence(fields, confidence, doc_type.value)

    if overall >= settings.threshold_l3:
        return _result(fields, confidence, overall, 3, slm_model, raw_text, start, True), doc_type, doc_type_confidence

    # ── Nível 4: Claude ───────────────────────────────────────────────────────
    from app.pipeline.levels.level4_claude import extract as claude_extract
    cl_fields, cl_confidence, cl_model = await claude_extract(
        raw_text, doc_type.value, fields, confidence
    )
    fields, confidence = _merge(fields, confidence, cl_fields, cl_confidence)
    overall = compute_overall_confidence(fields, confidence, doc_type.value)

    return _result(fields, confidence, overall, 4, cl_model, raw_text, start, True), doc_type, doc_type_confidence


def _result(
    fields, confidence, overall, level, model, raw_text, start, needs_loop
) -> ExtractionResult:
    return ExtractionResult(
        fields=fields,
        confidence_scores=confidence,
        overall_confidence=overall,
        level_used=level,
        model_used=model,
        raw_text=raw_text,
        processing_ms=int((time.monotonic() - start) * 1000),
        needs_learning_loop=needs_loop,
    )


def _merge(
    fields: dict, confidence: dict,
    new_fields: dict, new_confidence: dict,
) -> tuple[dict, dict]:
    """Merge: campo novo só substitui se tiver confiança maior."""
    result_fields = dict(fields)
    result_confidence = dict(confidence)
    for k, v in new_fields.items():
        if new_confidence.get(k, 0) > result_confidence.get(k, 0):
            result_fields[k] = v
            result_confidence[k] = new_confidence[k]
    return result_fields, result_confidence
