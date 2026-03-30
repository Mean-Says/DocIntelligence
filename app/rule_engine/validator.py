"""
Valida uma regex candidata via Groq (modelo diferente do gerador para evitar viés).
Também faz validação estrutural local (CNPJ checksum, parse de data, etc).
"""
import json
import re
from groq import AsyncGroq
from app.config import settings
from app.utils.normalizers import apply as normalize

_SYSTEM = """Você é um validador de regex para extração de documentos.
Dado uma regex, um valor esperado e um trecho de texto, verifique se a regex extrai o valor corretamente.
Responda APENAS com JSON válido."""

_USER_TEMPLATE = """Regex: {pattern}
Capture group: {capture_group}
Valor esperado: "{expected}"
Normalizer: {normalizer}

Trecho do texto:
---
{excerpt}
---

Aplique a regex ao texto. A regex extrai "{expected}" (após normalização)?
Retorne JSON:
{{
  "match": <true|false>,
  "extracted_raw": "<o que a regex captura ou null>",
  "extracted_normalized": "<após normalizer ou null>",
  "confidence": <0.0-1.0>,
  "reason": "<explicação>"
}}"""


async def validate_rule_candidate(
    pattern: str,
    capture_group: int,
    normalizer: str,
    expected_value: str,
    raw_text: str,
) -> dict:
    """
    Retorna dict com {match, confidence, reason, structural_ok}.
    """
    excerpt = raw_text[:3000]

    # Validação local primeiro (mais barata)
    local_result = _validate_locally(pattern, capture_group, normalizer, expected_value, raw_text)

    # Se falhou localmente, confiança baixa — não precisa chamar AI
    if not local_result["match"]:
        return {
            "match": False,
            "confidence": 0.0,
            "reason": f"regex não casou localmente: {local_result['reason']}",
            "structural_ok": False,
        }

    # Validação estrutural (CNPJ checksum, data válida, etc)
    structural_ok = _structural_validate(local_result.get("extracted_normalized", ""), expected_value)

    # Validação cruzada via Groq
    client = AsyncGroq(api_key=settings.groq_api_key)
    try:
        response = await client.chat.completions.create(
            model=settings.validator_model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _USER_TEMPLATE.format(
                    pattern=pattern,
                    capture_group=capture_group,
                    expected=expected_value,
                    normalizer=normalizer,
                    excerpt=excerpt,
                )},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        confidence = float(result.get("confidence", 0.0))

        # Penaliza se a validação estrutural falhou
        if not structural_ok:
            confidence *= 0.7

        return {
            "match": result.get("match", False),
            "confidence": confidence,
            "reason": result.get("reason", ""),
            "structural_ok": structural_ok,
        }

    except Exception as e:
        # Se Groq falhar, usa só resultado local com confiança reduzida
        return {
            "match": local_result["match"],
            "confidence": 0.65 if local_result["match"] else 0.0,
            "reason": f"validação local apenas (groq indisponível): {e}",
            "structural_ok": structural_ok,
        }


def _validate_locally(
    pattern: str,
    capture_group: int,
    normalizer: str,
    expected_value: str,
    text: str,
) -> dict:
    try:
        compiled = re.compile(pattern, re.IGNORECASE | re.DOTALL)
        match = compiled.search(text)
        if not match:
            return {"match": False, "reason": "sem match no texto"}

        try:
            raw = match.group(capture_group)
        except IndexError:
            raw = match.group(0)

        normalized = normalize(normalizer, raw)

        # Compara ignorando case e espaços extras
        matches = normalized.strip().lower() == expected_value.strip().lower()
        return {
            "match": matches,
            "extracted_raw": raw,
            "extracted_normalized": normalized,
            "reason": "match" if matches else f"extraiu '{normalized}', esperava '{expected_value}'",
        }
    except re.error as e:
        return {"match": False, "reason": f"regex inválida: {e}"}


def _structural_validate(extracted: str, expected: str) -> bool:
    """Validações de integridade por tipo de dado."""
    digits = re.sub(r"\D", "", extracted)

    # CNPJ: 14 dígitos com checksum
    if len(digits) == 14:
        return _cnpj_valid(digits)

    # CPF: 11 dígitos com checksum
    if len(digits) == 11:
        return _cpf_valid(digits)

    # Data ISO: deve ser parseável
    if re.match(r"\d{4}-\d{2}-\d{2}", extracted):
        from datetime import datetime
        try:
            datetime.strptime(extracted[:10], "%Y-%m-%d")
            return True
        except ValueError:
            return False

    # Valor monetário: deve ser número positivo
    try:
        val = float(extracted.replace(",", "."))
        return val > 0
    except (ValueError, AttributeError):
        pass

    return True  # sem validação estrutural específica


def _cnpj_valid(cnpj: str) -> bool:
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    def digit(nums, weights):
        total = sum(int(n) * w for n, w in zip(nums, weights))
        rem = total % 11
        return 0 if rem < 2 else 11 - rem

    return (
        digit(cnpj[:12], weights1) == int(cnpj[12]) and
        digit(cnpj[:13], weights2) == int(cnpj[13])
    )


def _cpf_valid(cpf: str) -> bool:
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    def digit(nums, length):
        total = sum(int(n) * (length + 1 - i) for i, n in enumerate(nums[:length]))
        rem = (total * 10) % 11
        return 0 if rem == 10 else rem

    return (
        digit(cpf, 9) == int(cpf[9]) and
        digit(cpf, 10) == int(cpf[10])
    )
