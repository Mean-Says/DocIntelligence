"""
Testes HTTP da API — testa a camada de rota, autenticação e serialização.
Pipeline mockado para não depender de AI ou arquivos reais.
"""
import io
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.models.document import Document, DocumentStatus, DocumentType, FileType
from app.models.extraction import Extraction


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, test_client):
        response = await test_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestAuth:
    @pytest.mark.asyncio
    async def test_extract_without_token_returns_403(self, test_client):
        response = await test_client.post("/v1/extract", files={"file": ("test.pdf", b"fake", "application/pdf")})
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_extract_with_invalid_token_returns_401(self, test_client):
        response = await test_client.post(
            "/v1/extract",
            headers={"Authorization": "Bearer invalid-token"},
            files={"file": ("test.pdf", b"fake", "application/pdf")},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token_passes_auth(self, test_client, sample_client, mock_r2):
        _, raw_key = sample_client

        mock_job = MagicMock()
        mock_job.job_id = "test-job-id"

        with (
            patch("app.api.v1.extract.create_pool", AsyncMock()) as mock_pool_factory,
        ):
            mock_pool = AsyncMock()
            mock_pool.enqueue_job = AsyncMock(return_value=mock_job)
            mock_pool.close = AsyncMock()
            mock_pool_factory.return_value = mock_pool

            response = await test_client.post(
                "/v1/extract",
                headers={"Authorization": f"Bearer {raw_key}"},
                files={"file": ("test.pdf", b"%PDF-1.4 fake content", "application/pdf")},
            )

        assert response.status_code in (202, 422, 500)  # passou a auth


class TestExtract:
    @pytest.mark.asyncio
    async def test_returns_202_with_job_id(self, test_client, sample_client, mock_r2):
        _, raw_key = sample_client

        mock_job = MagicMock()
        mock_job.job_id = "arq:job:test-123"

        with (
            patch("app.api.v1.extract.create_pool", AsyncMock()) as mock_pool_factory,
        ):
            mock_pool = AsyncMock()
            mock_pool.enqueue_job = AsyncMock(return_value=mock_job)
            mock_pool.close = AsyncMock()
            mock_pool_factory.return_value = mock_pool

            response = await test_client.post(
                "/v1/extract",
                headers={"Authorization": f"Bearer {raw_key}"},
                files={"file": ("nota.pdf", b"%PDF-1.4 content", "application/pdf")},
            )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert "document_id" in data
        assert "status_url" in data
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_rejects_oversized_file(self, test_client, sample_client):
        _, raw_key = sample_client

        # 51MB de dados
        big_content = b"x" * (51 * 1024 * 1024)

        response = await test_client.post(
            "/v1/extract",
            headers={"Authorization": f"Bearer {raw_key}"},
            files={"file": ("big.pdf", big_content, "application/pdf")},
        )

        assert response.status_code == 413

    @pytest.mark.asyncio
    async def test_rejects_unsupported_mime_type(self, test_client, sample_client, mock_r2):
        _, raw_key = sample_client

        response = await test_client.post(
            "/v1/extract",
            headers={"Authorization": f"Bearer {raw_key}"},
            files={"file": ("doc.xlsx", b"fake excel", "application/vnd.ms-excel")},
        )

        assert response.status_code == 415


class TestJobPolling:
    @pytest_asyncio.fixture
    async def done_document(self, test_session, sample_client):
        client, _ = sample_client
        doc_id = str(uuid.uuid4())

        doc = Document(
            id=doc_id,
            client_id=client.id,
            file_name="nfe_test.pdf",
            file_type=FileType.PDF_BINARY,
            storage_key=f"clients/{client.id}/{doc_id}.pdf",
            doc_type=DocumentType.NFE,
            doc_type_confidence=0.95,
            status=DocumentStatus.DONE,
            processing_level=2,
            job_id="test-job-done",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        extraction = Extraction(
            id=str(uuid.uuid4()),
            document_id=doc_id,
            fields={
                "cnpj_emitente": "12345678000199",
                "valor_total": "1250.0",
                "data_emissao": "2026-03-15",
                "numero_nf": "000123456",
            },
            confidence_scores={
                "cnpj_emitente": 0.92,
                "valor_total": 0.90,
                "data_emissao": 0.91,
                "numero_nf": 0.93,
            },
            overall_confidence=0.915,
            level_used=2,
            processing_ms=87,
            created_at=datetime.utcnow(),
        )
        test_session.add(doc)
        test_session.add(extraction)
        await test_session.commit()
        return doc

    @pytest.mark.asyncio
    async def test_polling_done_job_returns_result(self, test_client, sample_client, done_document):
        _, raw_key = sample_client

        response = await test_client.get(
            f"/v1/extract/jobs/{done_document.job_id}",
            headers={"Authorization": f"Bearer {raw_key}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "done"
        assert data["processing_level"] == 2
        assert data["data"]["cnpj_emitente"] == "12345678000199"
        assert data["data"]["valor_total"] == "1250.0"
        assert data["overall_confidence"] == pytest.approx(0.915)

    @pytest.mark.asyncio
    async def test_polling_pending_job_returns_pending(self, test_client, sample_client, test_session):
        client, raw_key = sample_client
        doc_id = str(uuid.uuid4())

        doc = Document(
            id=doc_id,
            client_id=client.id,
            file_name="pending.pdf",
            storage_key=f"clients/{client.id}/{doc_id}.pdf",
            status=DocumentStatus.PENDING,
            job_id="test-job-pending",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        test_session.add(doc)
        await test_session.commit()

        response = await test_client.get(
            "/v1/extract/jobs/test-job-pending",
            headers={"Authorization": f"Bearer {raw_key}"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "pending"

    @pytest.mark.asyncio
    async def test_polling_job_from_another_client_returns_404(self, test_client, sample_client, test_session):
        """Cliente A não deve ver jobs do cliente B."""
        _, raw_key = sample_client

        # Documento de outro cliente
        other_client_id = str(uuid.uuid4())
        doc = Document(
            id=str(uuid.uuid4()),
            client_id=other_client_id,
            file_name="other.pdf",
            storage_key="clients/other/doc.pdf",
            status=DocumentStatus.DONE,
            job_id="other-client-job",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        test_session.add(doc)
        await test_session.commit()

        response = await test_client.get(
            "/v1/extract/jobs/other-client-job",
            headers={"Authorization": f"Bearer {raw_key}"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_polling_nonexistent_job_returns_404(self, test_client, sample_client):
        _, raw_key = sample_client

        response = await test_client.get(
            "/v1/extract/jobs/nonexistent-job-id",
            headers={"Authorization": f"Bearer {raw_key}"},
        )

        assert response.status_code == 404


class TestFeedback:
    @pytest_asyncio.fixture
    async def done_doc_with_extraction(self, test_session, sample_client):
        client, _ = sample_client
        doc_id = str(uuid.uuid4())

        doc = Document(
            id=doc_id,
            client_id=client.id,
            file_name="nfe.pdf",
            storage_key=f"clients/{client.id}/{doc_id}.pdf",
            status=DocumentStatus.DONE,
            job_id="job-feedback-test",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        extraction = Extraction(
            id=str(uuid.uuid4()),
            document_id=doc_id,
            fields={"valor_total": "999.00"},
            confidence_scores={"valor_total": 0.75},
            overall_confidence=0.75,
            level_used=3,  # AI — vai disparar relearn
            processing_ms=200,
            created_at=datetime.utcnow(),
        )
        test_session.add(doc)
        test_session.add(extraction)
        await test_session.commit()
        return doc_id

    @pytest.mark.asyncio
    async def test_feedback_accepted(self, test_client, sample_client, done_doc_with_extraction):
        _, raw_key = sample_client

        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock()
        mock_pool.close = AsyncMock()

        with patch("app.api.v1.feedback.create_pool", AsyncMock(return_value=mock_pool)):
            response = await test_client.post(
                "/v1/feedback",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={
                    "document_id": done_doc_with_extraction,
                    "field": "valor_total",
                    "correct_value": "1250.00",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["accepted"] is True

    @pytest.mark.asyncio
    async def test_feedback_triggers_relearn_when_wrong(self, test_client, sample_client, done_doc_with_extraction):
        _, raw_key = sample_client

        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock()
        mock_pool.close = AsyncMock()

        with patch("app.api.v1.feedback.create_pool", AsyncMock(return_value=mock_pool)):
            response = await test_client.post(
                "/v1/feedback",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={
                    "document_id": done_doc_with_extraction,
                    "field": "valor_total",
                    "correct_value": "1250.00",  # diferente de "999.00"
                },
            )

        data = response.json()
        assert data["triggered_relearn"] is True
        mock_pool.enqueue_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_feedback_on_document_from_another_client_returns_404(
        self, test_client, sample_client, test_session
    ):
        _, raw_key = sample_client
        other_doc_id = str(uuid.uuid4())

        doc = Document(
            id=other_doc_id,
            client_id="other-client-id",
            file_name="other.pdf",
            storage_key="clients/other/doc.pdf",
            status=DocumentStatus.DONE,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        test_session.add(doc)
        await test_session.commit()

        response = await test_client.post(
            "/v1/feedback",
            headers={"Authorization": f"Bearer {raw_key}"},
            json={"document_id": other_doc_id, "field": "valor_total", "correct_value": "100.00"},
        )

        assert response.status_code == 404


# Import necessário para mock
from unittest.mock import MagicMock
