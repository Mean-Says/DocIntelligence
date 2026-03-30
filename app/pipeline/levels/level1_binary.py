"""
Nível 1: extração binária de PDF com pdfplumber + padrões universais.
Custo: zero. Instantâneo.
"""
import re
from app.utils.normalizers import apply as normalize

# Padrões universais que funcionam em qualquer documento
_UNIVERSAL_PATTERNS: list[tuple[str, str, str]] = [
    # (field_name, regex, normalizer)
    ("cpf", r"\b(\d{3}\.?\d{3}\.?\d{3}-?\d{2})\b", "digits_only"),
    ("cnpj", r"\b(\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2})\b", "digits_only"),
    ("email", r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", "strip"),
    ("date", r"\b(\d{2}[\/\-]\d{2}[\/\-]\d{4})\b", "date_iso"),
    ("phone", r"\(?\d{2}\)?\s?\d{4,5}[\-\s]?\d{4}", "digits_only"),
]


def extract(raw_text: str) -> tuple[dict[str, str], dict[str, float]]:
    """
    Aplica padrões universais no texto bruto.
    Retorna (fields, confidence_scores).
    Usado como base antes do rule engine do Nível 2.
    """
    fields: dict[str, str] = {}
    confidence: dict[str, float] = {}

    for field_name, pattern, normalizer in _UNIVERSAL_PATTERNS:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            value = normalize(normalizer, match.group(1) if match.lastindex else match.group(0))
            if value:
                fields[field_name] = value
                confidence[field_name] = 0.80  # padrões universais têm confiança base menor

    return fields, confidence
