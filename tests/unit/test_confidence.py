import pytest
from app.utils.confidence import compute_overall_confidence, missing_required_fields


class TestComputeOverallConfidence:
    def test_all_required_fields_high_confidence(self):
        fields = {
            "cnpj_emitente": "12345678000199",
            "valor_total": "1250.00",
            "data_emissao": "2026-03-15",
            "numero_nf": "000123",
        }
        scores = {k: 0.95 for k in fields}
        result = compute_overall_confidence(fields, scores, "nfe")
        assert result >= 0.90

    def test_missing_required_field_lowers_score(self):
        fields = {
            "valor_total": "1250.00",
            "data_emissao": "2026-03-15",
            "numero_nf": "000123",
            # cnpj_emitente ausente
        }
        scores = {k: 0.95 for k in fields}
        result = compute_overall_confidence(fields, scores, "nfe")
        assert result < 0.85

    def test_all_required_missing_returns_zero_or_low(self):
        result = compute_overall_confidence({}, {}, "nfe")
        assert result <= 0.10

    def test_field_below_floor_contributes_zero(self):
        fields = {
            "cnpj_emitente": "12345678000199",
            "valor_total": "1250.00",
            "data_emissao": "2026-03-15",
            "numero_nf": "000123",
        }
        # cnpj com confiança abaixo do floor (0.40)
        scores = {k: 0.95 for k in fields}
        scores["cnpj_emitente"] = 0.20
        score_with_low = compute_overall_confidence(fields, scores, "nfe")

        scores["cnpj_emitente"] = 0.95
        score_with_high = compute_overall_confidence(fields, scores, "nfe")

        assert score_with_low < score_with_high

    def test_unknown_doc_type_uses_simple_average(self):
        fields = {"campo_a": "val", "campo_b": "val"}
        scores = {"campo_a": 0.80, "campo_b": 0.60}
        result = compute_overall_confidence(fields, scores, "unknown")
        assert 0.65 <= result <= 0.75

    def test_curriculo_requires_nome_and_email(self):
        fields = {"email": "test@example.com"}
        scores = {"email": 0.99}
        # nome ausente — penaliza
        without_nome = compute_overall_confidence(fields, scores, "curriculo")

        fields["nome"] = "João Silva"
        scores["nome"] = 0.99
        with_nome = compute_overall_confidence(fields, scores, "curriculo")

        assert with_nome > without_nome

    def test_score_never_exceeds_1(self):
        fields = {
            "cnpj_emitente": "12345678000199",
            "valor_total": "1250.00",
            "data_emissao": "2026-03-15",
            "numero_nf": "000123",
        }
        scores = {k: 1.0 for k in fields}
        result = compute_overall_confidence(fields, scores, "nfe")
        assert result <= 1.0

    def test_score_never_below_zero(self):
        result = compute_overall_confidence({}, {}, "contrato")
        assert result >= 0.0


class TestMissingRequiredFields:
    def test_all_present(self):
        fields = {
            "cnpj_emitente": "12345678000199",
            "valor_total": "1250.00",
            "data_emissao": "2026-03-15",
            "numero_nf": "000123",
        }
        assert missing_required_fields(fields, "nfe") == []

    def test_some_missing(self):
        fields = {"cnpj_emitente": "12345678000199"}
        missing = missing_required_fields(fields, "nfe")
        assert "valor_total" in missing
        assert "data_emissao" in missing
        assert "cnpj_emitente" not in missing

    def test_empty_value_counts_as_missing(self):
        fields = {"cnpj_emitente": "", "valor_total": "1250.00", "data_emissao": "2026-03-15", "numero_nf": "123"}
        missing = missing_required_fields(fields, "nfe")
        assert "cnpj_emitente" in missing

    def test_unknown_doc_type_returns_empty(self):
        assert missing_required_fields({"qualquer": "coisa"}, "unknown") == []
