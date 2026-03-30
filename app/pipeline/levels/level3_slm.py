"""
Nível 3: extração via SLM (Groq / Llama 3.3 70B).
"""
import json
from groq import AsyncGroq
from app.config import settings

_SYSTEM_PROMPT = """Você é um extrator especializado de documentos.
Dado o texto de um documento, extraia os campos solicitados e retorne APENAS JSON válido.
Para cada campo, inclua o valor extraído e um score de confiança entre 0.0 e 1.0.
Se um campo não for encontrado, não o inclua no resultado.
Formato: {"fields": {"campo": "valor"}, "confidence": {"campo": 0.95}}"""


async def extract(
    text: str,
    doc_type: str,
    existing_fields: dict,
    existing_confidence: dict,
) -> tuple[dict[str, str], dict[str, float], str]:
    """
    Retorna (fields, confidence_scores, model_name).
    Já mergedos com existing: SLM preenche apenas os campos faltantes ou com baixa confiança.
    """
    from app.utils.confidence import REQUIRED_FIELDS
    required = REQUIRED_FIELDS.get(doc_type, [])
    missing = [f for f in required if f not in existing_fields]

    if not missing:
        return {}, {}, settings.validator_model

    client = AsyncGroq(api_key=settings.groq_api_key)

    # Envia apenas 3000 chars para economizar tokens
    text_excerpt = text[:3000]

    user_prompt = f"""Tipo de documento: {doc_type}
Campos a extrair: {', '.join(missing)}

Texto do documento:
---
{text_excerpt}
---"""

    response = await client.chat.completions.create(
        model=settings.validator_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)

    fields = data.get("fields", {})
    confidence = data.get("confidence", {})

    # Normaliza confidence para floats
    confidence = {k: float(v) for k, v in confidence.items()}

    return fields, confidence, settings.validator_model
