"""
Fixtures compartilhadas entre todos os testes.
"""
import hashlib
import uuid
from datetime import datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.main import app
from app.deps import get_session
from app.models.client import Client

# ── Banco de dados em memória (aiosqlite) ─────────────────────────────────────
# Nota: usamos SQLite apenas para testes — JSONB columns são declaradas
# como JSON no SQLite. Campos que usam JSONB funcionam normalmente.

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def test_client(test_session) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client com DB de teste injetado."""

    async def override_session():
        yield test_session

    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


# ── Fixtures de dados ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def sample_client(test_session) -> tuple[Client, str]:
    """Cria um cliente de teste e retorna (Client, raw_api_key)."""
    raw_key = f"test-key-{uuid.uuid4()}"
    hashed = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()
    lookup = hashlib.sha256(raw_key.encode()).hexdigest()

    client = Client(
        id=str(uuid.uuid4()),
        name="Test Client",
        api_key_hash=hashed,
        api_key_lookup=lookup,
        plan="starter",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    test_session.add(client)
    await test_session.commit()
    await test_session.refresh(client)
    return client, raw_key


@pytest.fixture
def auth_headers(sample_client):
    """Retorna headers de autenticação para o cliente de teste."""
    _, raw_key = sample_client
    return {"Authorization": f"Bearer {raw_key}"}


# ── Mocks de AI e Storage ─────────────────────────────────────────────────────

@pytest.fixture
def mock_r2(monkeypatch):
    """Mock do R2: upload e download não fazem nada."""
    monkeypatch.setattr("app.storage.r2.upload", AsyncMock(return_value="clients/test/doc.pdf"))
    monkeypatch.setattr("app.storage.r2.download", AsyncMock())
    monkeypatch.setattr("app.storage.r2.delete", AsyncMock())


@pytest.fixture
def mock_groq(monkeypatch):
    """Mock do Groq: retorna campos com confiança alta."""
    async def fake_groq_extract(text, doc_type, existing_fields, existing_confidence):
        return (
            {"valor_total": "1250.00", "data_emissao": "2026-03-15"},
            {"valor_total": 0.88, "data_emissao": 0.85},
            "llama-3.3-70b-versatile",
        )
    monkeypatch.setattr("app.pipeline.levels.level3_slm.extract", fake_groq_extract)


@pytest.fixture
def mock_claude(monkeypatch):
    """Mock do Claude: retorna todos os campos de NF-e com confiança alta."""
    async def fake_claude_extract(text, doc_type, existing_fields, existing_confidence):
        return (
            {
                "cnpj_emitente": "12345678000199",
                "valor_total": "1250.00",
                "data_emissao": "2026-03-15",
                "numero_nf": "000123456",
            },
            {
                "cnpj_emitente": 0.97,
                "valor_total": 0.95,
                "data_emissao": 0.93,
                "numero_nf": 0.96,
            },
            "claude-sonnet-4-6",
        )
    monkeypatch.setattr("app.pipeline.levels.level4_claude.extract", fake_claude_extract)
