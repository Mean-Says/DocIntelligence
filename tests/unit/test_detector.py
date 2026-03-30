import pytest
from app.pipeline.detector import detect_doc_type
from app.models.document import DocumentType


class TestDetectDocType:
    def test_detects_nfe(self):
        text = """
        NOTA FISCAL ELETRÔNICA - NF-e
        DANFE - Documento Auxiliar da Nota Fiscal Eletrônica
        CHAVE DE ACESSO: 1234 5678 9012
        CNPJ Emitente: 12.345.678/0001-99
        """
        doc_type, confidence = detect_doc_type(text)
        assert doc_type == DocumentType.NFE
        assert confidence >= 0.60

    def test_detects_curriculo(self):
        text = """
        CURRÍCULO VITAE
        João Silva — Desenvolvedor Senior
        Experiência Profissional:
        2020-2024: Empresa ABC — Engenheiro de Software
        Formação Acadêmica: Ciência da Computação — USP
        Habilidades: Python, FastAPI, PostgreSQL
        """
        doc_type, confidence = detect_doc_type(text)
        assert doc_type == DocumentType.CURRICULO
        assert confidence >= 0.60

    def test_detects_conta_luz(self):
        text = """
        CONTA DE ENERGIA ELÉTRICA
        Distribuidora: CPFL Energia
        Leitura Anterior: 1234 kWh
        Leitura Atual: 1456 kWh
        Consumo kWh: 222
        Fatura de Energia — Vencimento: 15/04/2026
        """
        doc_type, confidence = detect_doc_type(text)
        assert doc_type == DocumentType.CONTA_LUZ
        assert confidence >= 0.60

    def test_detects_contrato(self):
        text = """
        CONTRATO DE PRESTAÇÃO DE SERVIÇOS
        Pelo presente instrumento particular, as partes:
        CLÁUSULA PRIMEIRA — DO OBJETO
        CLÁUSULA SEGUNDA — DO VALOR
        Foro competente: Comarca de São Paulo
        """
        doc_type, confidence = detect_doc_type(text)
        assert doc_type == DocumentType.CONTRATO
        assert confidence >= 0.60

    def test_returns_unknown_for_unrecognized(self):
        text = "Este é um texto genérico sem nenhuma palavra-chave reconhecível."
        doc_type, confidence = detect_doc_type(text)
        assert doc_type == DocumentType.UNKNOWN

    def test_returns_unknown_for_empty_text(self):
        doc_type, confidence = detect_doc_type("")
        assert doc_type == DocumentType.UNKNOWN
        assert confidence == 0.0

    def test_confidence_between_zero_and_one(self):
        text = "NOTA FISCAL ELETRÔNICA NF-e DANFE CHAVE DE ACESSO CNPJ"
        _, confidence = detect_doc_type(text)
        assert 0.0 <= confidence <= 1.0

    def test_nfe_wins_over_weak_curriculo_signals(self):
        # Texto claramente de NF-e com uma palavra em comum com currículo
        text = """
        NOTA FISCAL ELETRÔNICA - NF-e
        DANFE
        CHAVE DE ACESSO: 1234
        Valor Total: R$ 1.500,00
        """
        doc_type, _ = detect_doc_type(text)
        assert doc_type == DocumentType.NFE
