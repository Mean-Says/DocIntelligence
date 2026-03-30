REQUIRED_FIELDS: dict[str, list[str]] = {
    "nfe": ["cnpj_emitente", "valor_total", "data_emissao", "numero_nf"],
    "conta_luz": ["valor_total", "vencimento", "consumo_kwh"],
    "curriculo": ["nome", "email"],
    "contrato": ["partes", "valor", "prazo"],
}

FIELD_WEIGHTS: dict[str, dict[str, float]] = {
    "nfe": {
        "cnpj_emitente": 0.25,
        "valor_total": 0.30,
        "data_emissao": 0.20,
        "numero_nf": 0.25,
    },
    "conta_luz": {
        "valor_total": 0.40,
        "vencimento": 0.35,
        "consumo_kwh": 0.25,
    },
    "curriculo": {
        "nome": 0.40,
        "email": 0.35,
        "telefone": 0.15,
        "linkedin": 0.10,
    },
    "contrato": {
        "partes": 0.35,
        "valor": 0.30,
        "prazo": 0.35,
    },
}

# Confiança mínima por campo individual — abaixo disso, campo é ignorado
FIELD_FLOOR = 0.40


def compute_overall_confidence(
    fields: dict[str, str],
    confidence_scores: dict[str, float],
    doc_type: str,
) -> float:
    """
    Retorna confiança geral ponderada.
    Campos required ausentes contribuem 0.0 para o score.
    """
    weights = FIELD_WEIGHTS.get(doc_type, {})
    required = REQUIRED_FIELDS.get(doc_type, [])

    if not weights:
        # Sem pesos definidos: média simples dos campos presentes
        scores = [v for v in confidence_scores.values() if v >= FIELD_FLOOR]
        return sum(scores) / len(scores) if scores else 0.0

    total_weight = sum(weights.values())
    weighted_sum = 0.0

    for field, weight in weights.items():
        score = confidence_scores.get(field, 0.0)
        if score < FIELD_FLOOR:
            score = 0.0  # campo presente mas com confiança muito baixa = ignorado
        weighted_sum += score * weight

    # Penaliza campos required completamente ausentes
    for field in required:
        if field not in fields:
            field_weight = weights.get(field, 0.0)
            weighted_sum -= field_weight * 0.5  # penalidade extra por ausência

    return max(0.0, weighted_sum / total_weight)


def missing_required_fields(fields: dict[str, str], doc_type: str) -> list[str]:
    required = REQUIRED_FIELDS.get(doc_type, [])
    return [f for f in required if f not in fields or not fields[f]]
