import re
import pytest
from app.rule_engine.matcher import match
from app.rule_engine.loader import CompiledRule


def make_rule(field_name: str, pattern: str, confidence: float = 0.90, normalizer: str = "strip", capture_group: int = 1, priority: int = 10) -> CompiledRule:
    return CompiledRule(
        id="test-rule",
        field_name=field_name,
        pattern=re.compile(pattern, re.IGNORECASE),
        capture_group=capture_group,
        normalizer=normalizer,
        confidence_baseline=confidence,
        priority=priority,
    )


class TestMatch:
    def test_extracts_field_from_text(self):
        rules = [make_rule("cnpj", r"CNPJ[:\s]+([\d.\/\-]+)", normalizer="digits_only")]
        text = "Emitente: CNPJ: 12.345.678/0001-99\nRazão Social: Empresa X"
        fields, confidence = match(text, rules)

        assert fields["cnpj"] == "12345678000199"
        assert confidence["cnpj"] == 0.90

    def test_no_match_returns_empty(self):
        rules = [make_rule("cnpj", r"CNPJ[:\s]+([\d.\/\-]+)")]
        fields, confidence = match("Texto sem CNPJ aqui", rules)
        assert "cnpj" not in fields

    def test_higher_confidence_rule_wins(self):
        low = make_rule("email", r"email[:\s]+(\S+@\S+)", confidence=0.70)
        high = make_rule("email", r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", confidence=0.95)
        text = "Contato email: joao@empresa.com"
        fields, confidence = match(text, [low, high])

        assert fields["email"] == "joao@empresa.com"
        assert confidence["email"] == 0.95

    def test_does_not_overwrite_higher_confidence_existing(self):
        rule = make_rule("email", r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", confidence=0.70)
        text = "email: joao@empresa.com"
        existing_fields = {"email": "original@empresa.com"}
        existing_confidence = {"email": 0.95}

        fields, confidence = match(text, [rule], existing_fields, existing_confidence)

        assert fields["email"] == "original@empresa.com"
        assert confidence["email"] == 0.95

    def test_merges_multiple_fields(self):
        rules = [
            make_rule("email", r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})"),
            make_rule("cnpj", r"CNPJ[:\s]+([\d.\/\-]+)", normalizer="digits_only"),
        ]
        text = "CNPJ: 12.345.678/0001-99 | email: contato@empresa.com"
        fields, confidence = match(text, rules)

        assert "email" in fields
        assert "cnpj" in fields

    def test_normalizer_applied(self):
        # Padrão cobre "Data:" mas não "Data de Emissão:" — precisamos do padrão correto
        rules = [make_rule("data", r"Data(?:\s+\w+)*[:\s]+(\d{2}/\d{2}/\d{4})", normalizer="date_iso")]
        text = "Data de Emissão: 15/03/2026"
        fields, _ = match(text, rules)
        assert fields["data"] == "2026-03-15"

    def test_normalizer_not_applied_for_simple_label(self):
        # Regex específico para "Data:" (sem palavras entre Data e :)
        rules = [make_rule("data", r"Data:\s+(\d{2}/\d{2}/\d{4})", normalizer="date_iso")]
        text = "Data: 15/03/2026"
        fields, _ = match(text, rules)
        assert fields["data"] == "2026-03-15"

    def test_empty_normalized_value_not_stored(self):
        # Se o normalizer retorna string vazia, não armazena o campo
        rules = [make_rule("phone", r"Tel[:\s]+([\d\s]+)", normalizer="digits_only")]
        text = "Tel: "  # match mas captura string vazia
        fields, _ = match(text, rules)
        assert "phone" not in fields

    def test_preserves_existing_fields_not_matched(self):
        rules = [make_rule("cnpj", r"CNPJ[:\s]+([\d.\/\-]+)", normalizer="digits_only")]
        text = "CNPJ: 12.345.678/0001-99"
        existing = {"nome": "Empresa X"}
        existing_conf = {"nome": 0.99}

        fields, confidence = match(text, rules, existing, existing_conf)

        assert fields["nome"] == "Empresa X"
        assert confidence["nome"] == 0.99
        assert "cnpj" in fields

    def test_capture_group_zero_uses_full_match(self):
        rules = [make_rule("cnpj", r"\d{14}", capture_group=0, normalizer="strip")]
        text = "12345678000199"
        fields, _ = match(text, rules)
        assert fields["cnpj"] == "12345678000199"

    def test_case_insensitive_matching(self):
        rules = [make_rule("valor", r"valor total[:\s]+([\d,\.]+)", normalizer="currency_brl")]
        text = "VALOR TOTAL: 1.250,00"
        fields, _ = match(text, rules)
        assert "valor" in fields
