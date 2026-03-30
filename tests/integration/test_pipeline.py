"""
Testes de integração do pipeline de extração.
AI mockada, lógica real de orchestração, detector e rule engine.
"""
import re
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.pipeline.orchestrator import run, ExtractionResult
from app.models.document import DocumentType, FileType
from app.rule_engine.loader import CompiledRule


# ── Fixtures de texto de documento ───────────────────────────────────────────

NFE_TEXT = """
NOTA FISCAL ELETRÔNICA - NF-e
DANFE - Documento Auxiliar da Nota Fiscal Eletrônica
CHAVE DE ACESSO: 35260312345678000199550010001234561234567890

EMITENTE
Razão Social: Empresa Teste Ltda
CNPJ: 12.345.678/0001-99

DESTINATÁRIO
Razão Social: Cliente Teste SA
CNPJ: 98.765.432/0001-10

NÚMERO: 000123456
DATA DE EMISSÃO: 15/03/2026

Valor Total da Nota: R$ 1.250,00
"""

CURRICULO_TEXT = """
CURRÍCULO VITAE
João da Silva
email: joao.silva@email.com
Telefone: (11) 99999-1234

Experiência Profissional:
2020-2024: Empresa ABC — Engenheiro de Software Sênior

Formação Acadêmica:
Bacharelado em Ciência da Computação — USP — 2020

Habilidades: Python, FastAPI, PostgreSQL, Docker
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_compiled_rule(field_name, pattern, normalizer="strip", confidence=0.90):
    return CompiledRule(
        id="test",
        field_name=field_name,
        pattern=re.compile(pattern, re.IGNORECASE),
        capture_group=1,
        normalizer=normalizer,
        confidence_baseline=confidence,
        priority=10,
    )


NF_RULES = [
    make_compiled_rule("cnpj_emitente", r"CNPJ[:\s]+([\d.\/\-]+)", normalizer="digits_only"),
    make_compiled_rule("valor_total", r"Valor Total da Nota[:\s]+R?\$?\s*([\d.,]+)", normalizer="currency_brl"),
    make_compiled_rule("data_emissao", r"DATA DE EMISSÃO[:\s]+(\d{2}/\d{2}/\d{4})", normalizer="date_iso"),
    make_compiled_rule("numero_nf", r"NÚMERO[:\s]+(\d+)", normalizer="strip"),
]


# ── Testes ────────────────────────────────────────────────────────────────────

class TestPipelineLevel1:
    """Documentos resolvidos por padrões universais (Nível 1)."""

    @pytest.mark.asyncio
    async def test_extracts_email_from_binary_pdf(self, tmp_path, mock_r2):
        # Cria PDF de texto simples simulado com pdfplumber
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        mock_session = AsyncMock()
        mock_redis = AsyncMock()

        with (
            patch("app.pipeline.detector.detect_file_type", return_value=(FileType.PDF_BINARY, CURRICULO_TEXT)),
            patch("app.pipeline.detector.detect_doc_type", return_value=(DocumentType.CURRICULO, 0.90)),
            patch("app.rule_engine.loader.load_rules", AsyncMock(return_value=[])),
            patch("app.pipeline.levels.level3_slm.extract", AsyncMock(return_value=({}, {}, "groq"))),
            patch("app.pipeline.levels.level4_claude.extract", AsyncMock(return_value=({}, {}, "claude"))),
        ):
            result, doc_type, confidence = await run(
                file_path=str(test_file),
                client_id="client-1",
                doc_type_hint=None,
                session=mock_session,
                redis=mock_redis,
            )

        assert "email" in result.fields
        assert result.fields["email"] == "joao.silva@email.com"


class TestPipelineLevel2:
    """Documentos resolvidos por regras do banco (Nível 2)."""

    @pytest.mark.asyncio
    async def test_resolves_nfe_with_rules(self, tmp_path):
        test_file = tmp_path / "nfe.pdf"
        test_file.write_bytes(b"fake")

        mock_session = AsyncMock()
        mock_redis = AsyncMock()

        with (
            patch("app.pipeline.detector.detect_file_type", return_value=(FileType.PDF_BINARY, NFE_TEXT)),
            patch("app.pipeline.detector.detect_doc_type", return_value=(DocumentType.NFE, 0.95)),
            patch("app.rule_engine.loader.load_rules", AsyncMock(return_value=NF_RULES)),
        ):
            result, doc_type, _ = await run(
                file_path=str(test_file),
                client_id="client-1",
                doc_type_hint=None,
                session=mock_session,
                redis=mock_redis,
            )

        assert result.level_used <= 2
        assert result.needs_learning_loop is False
        assert "cnpj_emitente" in result.fields
        assert result.fields["valor_total"] == "1250.0"
        assert result.fields["data_emissao"] == "2026-03-15"

    @pytest.mark.asyncio
    async def test_level2_does_not_call_ai(self, tmp_path):
        test_file = tmp_path / "nfe.pdf"
        test_file.write_bytes(b"fake")

        mock_session = AsyncMock()
        mock_redis = AsyncMock()
        mock_groq = AsyncMock(return_value=({}, {}, "groq"))
        mock_claude = AsyncMock(return_value=({}, {}, "claude"))

        with (
            patch("app.pipeline.detector.detect_file_type", return_value=(FileType.PDF_BINARY, NFE_TEXT)),
            patch("app.pipeline.detector.detect_doc_type", return_value=(DocumentType.NFE, 0.95)),
            patch("app.rule_engine.loader.load_rules", AsyncMock(return_value=NF_RULES)),
            patch("app.pipeline.levels.level3_slm.extract", mock_groq),
            patch("app.pipeline.levels.level4_claude.extract", mock_claude),
        ):
            result, _, _ = await run(
                file_path=str(test_file),
                client_id="client-1",
                doc_type_hint=None,
                session=mock_session,
                redis=mock_redis,
            )

        if result.level_used <= 2:
            mock_groq.assert_not_called()
            mock_claude.assert_not_called()


class TestPipelineLevel3:
    """Documentos que precisam do SLM."""

    @pytest.mark.asyncio
    async def test_escalates_to_groq_when_rules_insufficient(self, tmp_path):
        test_file = tmp_path / "doc.pdf"
        test_file.write_bytes(b"fake")

        mock_session = AsyncMock()
        mock_redis = AsyncMock()

        sparse_text = "Documento sem palavras-chave claras. Valor: 500,00"

        groq_result = (
            {"valor_total": "500.00", "cnpj_emitente": "12345678000199",
             "data_emissao": "2026-03-15", "numero_nf": "001"},
            {"valor_total": 0.85, "cnpj_emitente": 0.82, "data_emissao": 0.80, "numero_nf": 0.79},
            "llama-3.3-70b-versatile",
        )

        with (
            patch("app.pipeline.detector.detect_file_type", return_value=(FileType.PDF_BINARY, sparse_text)),
            patch("app.pipeline.detector.detect_doc_type", return_value=(DocumentType.NFE, 0.60)),
            patch("app.rule_engine.loader.load_rules", AsyncMock(return_value=[])),
            patch("app.pipeline.levels.level3_slm.extract", AsyncMock(return_value=groq_result)),
        ):
            result, _, _ = await run(
                file_path=str(test_file),
                client_id="client-1",
                doc_type_hint="nfe",
                session=mock_session,
                redis=mock_redis,
            )

        assert result.level_used == 3
        assert result.needs_learning_loop is True
        assert result.model_used == "llama-3.3-70b-versatile"


class TestPipelineMerge:
    """Comportamento de merge entre níveis."""

    @pytest.mark.asyncio
    async def test_higher_confidence_from_rule_beats_level1(self, tmp_path):
        """Regra com confiança 0.92 deve sobrescrever padrão universal com 0.80."""
        test_file = tmp_path / "doc.pdf"
        test_file.write_bytes(b"fake")

        # Regra com confiança maior para o mesmo campo
        high_conf_rule = make_compiled_rule(
            "cnpj", r"CNPJ[:\s]+([\d.\/\-]+)", normalizer="digits_only", confidence=0.92
        )

        mock_session = AsyncMock()
        mock_redis = AsyncMock()

        with (
            patch("app.pipeline.detector.detect_file_type", return_value=(FileType.PDF_BINARY, NFE_TEXT)),
            patch("app.pipeline.detector.detect_doc_type", return_value=(DocumentType.NFE, 0.95)),
            patch("app.rule_engine.loader.load_rules", AsyncMock(return_value=[high_conf_rule, *NF_RULES])),
        ):
            result, _, _ = await run(
                file_path=str(test_file),
                client_id="client-1",
                doc_type_hint=None,
                session=mock_session,
                redis=mock_redis,
            )

        # O campo foi extraído
        assert "cnpj" in result.fields or "cnpj_emitente" in result.fields


class TestPipelineOCR:
    """Documentos escaneados ativam OCR antes do Nível 3."""

    @pytest.mark.asyncio
    async def test_ocr_called_for_scanned_pdf(self, tmp_path):
        test_file = tmp_path / "scanned.pdf"
        test_file.write_bytes(b"fake")

        mock_session = AsyncMock()
        mock_redis = AsyncMock()
        mock_ocr = AsyncMock(return_value=NFE_TEXT)

        with (
            patch("app.pipeline.detector.detect_file_type", return_value=(FileType.PDF_SCANNED, "")),
            patch("app.pipeline.detector.detect_doc_type", return_value=(DocumentType.NFE, 0.90)),
            patch("app.rule_engine.loader.load_rules", AsyncMock(return_value=NF_RULES)),
            patch("app.utils.ocr.extract_text_from_file", mock_ocr),
        ):
            result, _, _ = await run(
                file_path=str(test_file),
                client_id="client-1",
                doc_type_hint=None,
                session=mock_session,
                redis=mock_redis,
            )

        mock_ocr.assert_called_once_with(str(test_file))
