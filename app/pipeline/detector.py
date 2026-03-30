"""
Detecta tipo de arquivo e tipo de documento.
"""
import re
from pathlib import Path

import pdfplumber

from app.models.document import DocumentType, FileType

# Heurísticas por palavras-chave para detecção de tipo de documento
_DOC_TYPE_SIGNALS: list[tuple[DocumentType, list[str], float]] = [
    (
        DocumentType.NFE,
        ["NOTA FISCAL ELETRÔNICA", "NF-e", "DANFE", "CHAVE DE ACESSO", "cnpj emitente"],
        0.95,
    ),
    (
        DocumentType.CONTA_LUZ,
        ["CONTA DE ENERGIA", "FATURA DE ENERGIA", "kWh", "distribuidora", "leitura anterior"],
        0.90,
    ),
    (
        DocumentType.CURRICULO,
        ["currículo", "curriculum vitae", "experiência profissional", "formação acadêmica", "habilidades"],
        0.88,
    ),
    (
        DocumentType.CONTRATO,
        ["CONTRATO", "CLÁUSULA", "as partes", "pelo presente instrumento", "foro competente"],
        0.85,
    ),
]

_MIN_TEXT_CHARS_PER_PAGE = 100  # abaixo disso: PDF escaneado


def detect_file_type(file_path: str) -> tuple[FileType, str]:
    """
    Retorna (FileType, raw_text).
    raw_text pode ser vazio se for imagem pura.
    """
    suffix = Path(file_path).suffix.lower()

    if suffix not in (".pdf",):
        return FileType.IMAGE, ""

    try:
        with pdfplumber.open(file_path) as pdf:
            pages_text = [page.extract_text() or "" for page in pdf.pages]
            full_text = "\n".join(pages_text)
            avg_chars = len(full_text) / max(len(pdf.pages), 1)

            if avg_chars >= _MIN_TEXT_CHARS_PER_PAGE:
                return FileType.PDF_BINARY, full_text
            else:
                return FileType.PDF_SCANNED, full_text  # texto parcial pode ajudar
    except Exception:
        return FileType.PDF_SCANNED, ""


def detect_doc_type(text: str) -> tuple[DocumentType, float]:
    """
    Detecta tipo de documento por contagem de sinais no texto.
    Retorna (doc_type, confiança).
    """
    text_lower = text.lower()
    best_type = DocumentType.UNKNOWN
    best_score = 0.0

    for doc_type, signals, max_confidence in _DOC_TYPE_SIGNALS:
        matches = sum(1 for s in signals if s.lower() in text_lower)
        score = (matches / len(signals)) * max_confidence
        if score > best_score:
            best_score = score
            best_type = doc_type

    # Confiança mínima para aceitar a detecção
    if best_score < 0.30:
        return DocumentType.UNKNOWN, best_score

    return best_type, min(best_score, 1.0)
