"""
Gera regex candidata para um campo via LLM (Groq ou Anthropic).
"""
import json
import re
from app.config import settings

_SYSTEM = """Você é um especialista em extração de dados de documentos brasileiros via regex.
Dado o texto de um documento e o valor correto de um campo, crie uma regex Python que extraia esse campo de forma confiável.
Responda APENAS com JSON válido, sem texto adicional."""

_USER_TEMPLATE = """Tipo de documento: {doc_type}
Campo: {field_name}
Valor correto: "{value}"

Trecho do documento (2000 chars ao redor do valor):
---
{excerpt}
---

Crie uma regex que extraia "{value}" do campo "{field_name}".
Considere variações de espaço, maiúsculas/minúsculas e pontuação.

Retorne JSON:
{{
  "pattern": "<regex string>",
  "capture_group": <int, geralmente 1>,
  "normalizer": "<strip|digits_only|date_iso|currency_brl|none>",
  "explanation": "<por que esse padrão funciona>"
}}"""


async def generate_rule_candidate(
    doc_type: str,
    field_name: str,
    value: str,
    raw_text: str,
) -> dict | None:
    """
    Retorna dict com {pattern, capture_group, normalizer, explanation}
    ou None se falhar.
    """
    excerpt = _excerpt_around(raw_text, value)
    if not excerpt:
        excerpt = raw_text[:2000]

    user_content = _USER_TEMPLATE.format(
        doc_type=doc_type,
        field_name=field_name,
        value=value,
        excerpt=excerpt,
    )

    try:
        raw = await _call_llm(user_content)

        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]

        result = json.loads(raw.strip())

        # Valida que o padrão é regex válido antes de retornar
        re.compile(result["pattern"])
        return result

    except Exception:
        return None


async def _call_llm(user_content: str) -> str:
    if settings.extractor_provider == "anthropic":
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model=settings.extractor_model,
            max_tokens=512,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        )
        return message.content[0].text

    # Default: Groq
    from groq import AsyncGroq
    client = AsyncGroq(api_key=settings.groq_api_key)
    response = await client.chat.completions.create(
        model=settings.extractor_model,
        max_tokens=512,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def _excerpt_around(text: str, value: str, window: int = 1000) -> str:
    """Retorna trecho de ±window chars ao redor da primeira ocorrência do valor."""
    idx = text.lower().find(value.lower())
    if idx == -1:
        digits = re.sub(r"\D", "", value)
        if digits:
            idx = text.find(digits[:6])
    if idx == -1:
        return ""
    start = max(0, idx - window)
    end = min(len(text), idx + len(value) + window)
    return text[start:end]
