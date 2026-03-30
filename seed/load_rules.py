"""
Script de seed: carrega regras iniciais de seed/rules.json para o banco.
Executar após a migration: python seed/load_rules.py
"""
import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.models.rule import Rule, RuleScope, RuleStatus, RuleOrigin


async def load_rules() -> None:
    seed_path = Path(__file__).parent / "rules.json"
    rules_data = json.loads(seed_path.read_text())

    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        for rule_data in rules_data:
            # Não duplica se já existe uma regra handcrafted igual
            existing = await session.exec(
                select(Rule).where(
                    Rule.doc_type == rule_data["doc_type"],
                    Rule.field_name == rule_data["field_name"],
                    Rule.scope == RuleScope.GLOBAL,
                    Rule.origin == RuleOrigin.HANDCRAFTED,
                )
            )
            if existing.first():
                print(f"  skip  {rule_data['doc_type']}.{rule_data['field_name']} (já existe)")
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
            print(f"  added {rule_data['doc_type']}.{rule_data['field_name']}")

        await session.commit()
        print(f"\n✓ {len(rules_data)} regras processadas.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(load_rules())
