"""
Cria um cliente com API key.
Uso: python scripts/create_client.py --name "Radar de Empregos" [--plan starter]

A API key é exibida UMA VEZ — salve imediatamente.
"""
import asyncio
import hashlib
import secrets
import sys
import argparse
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import bcrypt
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from app.config import settings
from app.models.client import Client


def generate_api_key() -> str:
    """Gera token no formato di_sk_<32 bytes hex>."""
    return f"di_sk_{secrets.token_hex(32)}"


async def create_client(name: str, plan: str) -> tuple[Client, str]:
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Verifica se já existe cliente com esse nome
        existing = await session.exec(select(Client).where(Client.name == name))
        if existing.first():
            print(f"\n⚠️  Já existe um cliente com o nome '{name}'.")
            print("Use um nome diferente ou delete o existente primeiro.")
            await engine.dispose()
            sys.exit(1)

        raw_key = generate_api_key()
        hashed = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt(rounds=12)).decode()
        lookup = hashlib.sha256(raw_key.encode()).hexdigest()

        client = Client(
            id=str(uuid.uuid4()),
            name=name,
            api_key_hash=hashed,
            api_key_lookup=lookup,
            plan=plan,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        session.add(client)
        await session.commit()
        await session.refresh(client)

    await engine.dispose()
    return client, raw_key


def main():
    parser = argparse.ArgumentParser(description="Cria um cliente DocIntelligence")
    parser.add_argument("--name", required=True, help="Nome do cliente")
    parser.add_argument("--plan", default="starter", choices=["free", "starter", "pro"], help="Plano")
    args = parser.parse_args()

    client, raw_key = asyncio.run(create_client(args.name, args.plan))

    print("\n" + "=" * 60)
    print(f"  Cliente criado com sucesso!")
    print("=" * 60)
    print(f"  Nome:  {client.name}")
    print(f"  ID:    {client.id}")
    print(f"  Plano: {client.plan}")
    print()
    print(f"  API KEY (salve agora — não será exibida novamente):")
    print(f"  {raw_key}")
    print("=" * 60 + "\n")
    print("  Uso:")
    print(f'  curl -H "Authorization: Bearer {raw_key}" ...')
    print()


if __name__ == "__main__":
    main()
