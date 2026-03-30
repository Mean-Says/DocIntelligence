"""
Aplica regras compiladas no texto extraído.
Hot path: todo documento resolvido localmente passa aqui.
"""
from app.rule_engine.loader import CompiledRule
from app.utils.normalizers import apply as normalize


def match(
    text: str,
    rules: list[CompiledRule],
    existing_fields: dict[str, str] | None = None,
    existing_confidence: dict[str, float] | None = None,
) -> tuple[dict[str, str], dict[str, float]]:
    """
    Aplica todas as regras no texto.
    Não sobrescreve campo já encontrado com confiança maior.

    Retorna (fields, confidence_scores) mergeados com existentes.
    """
    fields = dict(existing_fields or {})
    confidence = dict(existing_confidence or {})

    for rule in rules:
        match = rule.pattern.search(text)
        if not match:
            continue

        try:
            raw_value = match.group(rule.capture_group)
        except IndexError:
            raw_value = match.group(0)

        value = normalize(rule.normalizer, raw_value)
        if not value:
            continue

        # Só substitui se a nova confiança for maior que a atual
        current_confidence = confidence.get(rule.field_name, 0.0)
        if rule.confidence_baseline > current_confidence:
            fields[rule.field_name] = value
            confidence[rule.field_name] = rule.confidence_baseline

    return fields, confidence
