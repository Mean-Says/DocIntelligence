"""
Nível 4: extração via LLM (Groq ou Anthropic). Último recurso.
"""
import json
from app.config import settings

_SYSTEM_PROMPT = """Você é um extrator especializado de documentos brasileiros.
Dado o texto de um documento, extraia os campos solicitados com máxima precisão.
Retorne APENAS JSON válido, sem texto adicional.
Formato: {"fields": {"campo": "valor"}, "confidence": {"campo": 0.95}}
Para campos não encontrados, não os inclua. Seja conservador nos scores de confiança."""


async def extract(
    text: str,
    doc_type: str,
    existing_fields: dict,
    existing_confidence: dict,
) -> tuple[dict[str, str], dict[str, float], str]:
    """
    Retorna (fields, confidence_scores, model_name).
    Tenta extrair todos os campos — não apenas os faltantes — para máxima qualidade.
    """
    from app.utils.confidence import REQUIRED_FIELDS
    required = REQUIRED_FIELDS.get(doc_type, [])

    text_excerpt = text[:8000]

    user_prompt = f"""Tipo de documento: {doc_type}
Campos necessários: {', '.join(required)}

Texto do documento:
---
{text_excerpt}
---

Extraia os campos acima."""

    raw = await _call_llm(user_prompt)

    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0]
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0]

    data = json.loads(raw.strip())
    fields = data.get("fields", {})
    confidence = {k: float(v) for k, v in data.get("confidence", {}).items()}

    return fields, confidence, settings.extractor_model


async def _call_llm(user_prompt: str) -> str:
    if settings.extractor_provider == "anthropic":
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model=settings.extractor_model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text

    # Default: Groq
    from groq import AsyncGroq
    client = AsyncGroq(api_key=settings.groq_api_key)
    response = await client.chat.completions.create(
        model=settings.extractor_model,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content
