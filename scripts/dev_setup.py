"""
Setup de desenvolvimento local com SQLite (sem Docker).
Cria banco, roda migrations, carrega seed e cria cliente Radar de Empregos.

Uso: python scripts/dev_setup.py
"""
import asyncio
import hashlib
import secrets
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Aponta para SQLite em dev
import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

import bcrypt
import json
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select

from app.models.client import Client
from app.models.rule import Rule, RuleScope, RuleStatus, RuleOrigin


DB_URL = "sqlite+aiosqlite:///./dev.db"
CLIENT_NAME = "Radar de Empregos"


async def setup():
    engine = create_async_engine(DB_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Cria tabelas
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    print("✓ Banco criado (dev.db)")

    async with async_session() as session:
        # Carrega regras seed
        seed_path = Path(__file__).parent.parent / "seed" / "rules.json"
        rules_data = json.loads(seed_path.read_text())
        added = 0
        for rule_data in rules_data:
            existing = await session.exec(
                select(Rule).where(
                    Rule.doc_type == rule_data["doc_type"],
                    Rule.field_name == rule_data["field_name"],
                    Rule.scope == RuleScope.GLOBAL,
                    Rule.origin == RuleOrigin.HANDCRAFTED,
                )
            )
            if existing.first():
                continue
            rule = Rule(
                id=str(uuid.uuid4()),
                doc_type=rule_data["doc_type"],
                field_name=rule_data["field_name"],
                scope=RuleScope(rule_data.get("scope", "global")),
                pattern=rule_data["pattern"],
                capture_group=rule_data.get("capture_group", 1),
                normalizer=rule_data.get("normalizer", "strip"),
                priority=rule_data.get("priority", 100),
                confidence_baseline=rule_data.get("confidence_baseline", 0.85),
                status=RuleStatus.ACTIVE,
                origin=RuleOrigin.HANDCRAFTED,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(rule)
            added += 1
        await session.commit()
        print(f"✓ {added} regras seed carregadas")

        # Cria cliente Radar de Empregos se não existir
        existing_client = await session.exec(
            select(Client).where(Client.name == CLIENT_NAME)
        )
        if existing_client.first():
            print(f"✓ Cliente '{CLIENT_NAME}' já existe")
        else:
            raw_key = f"di_sk_{secrets.token_hex(32)}"
            hashed = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt(rounds=12)).decode()
            lookup = hashlib.sha256(raw_key.encode()).hexdigest()

            client = Client(
                id=str(uuid.uuid4()),
                name=CLIENT_NAME,
                api_key_hash=hashed,
                api_key_lookup=lookup,
                plan="starter",
                is_active=True,
                created_at=datetime.utcnow(),
            )
            session.add(client)
            await session.commit()

            print(f"\n{'=' * 60}")
            print(f"  Cliente criado: {CLIENT_NAME}")
            print(f"  API KEY (salve agora):")
            print(f"  {raw_key}")
            print(f"{'=' * 60}\n")

            # Salva a key em .env.dev para facilitar
            env_dev = Path(__file__).parent.parent / ".env.dev"
            env_dev.write_text(
                f"DATABASE_URL=sqlite+aiosqlite:///./dev.db\n"
                f"RADAR_API_KEY={raw_key}\n"
            )
            print(f"  Key salva em .env.dev para referência.")

    await engine.dispose()
    print("\n✓ Setup concluído. Para iniciar a API:")
    print("  DATABASE_URL=sqlite+aiosqlite:///./dev.db uvicorn app.main:app --reload")


if __name__ == "__main__":
    asyncio.run(setup())
