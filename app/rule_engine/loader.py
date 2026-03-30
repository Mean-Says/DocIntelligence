"""
Carrega regras do banco e mantém cache no Redis.
"""
import json
import re
from dataclasses import dataclass
from typing import Callable

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.config import settings
from app.models.rule import Rule, RuleStatus, RuleScope
from app.utils.normalizers import apply as normalize_fn, NORMALIZERS


@dataclass
class CompiledRule:
    id: str
    field_name: str
    pattern: re.Pattern
    capture_group: int
    normalizer: str
    confidence_baseline: float
    priority: int


def _compile(rule: Rule) -> CompiledRule:
    return CompiledRule(
        id=rule.id,
        field_name=rule.field_name,
        pattern=re.compile(rule.pattern, re.IGNORECASE | re.DOTALL),
        capture_group=rule.capture_group,
        normalizer=rule.normalizer,
        confidence_baseline=rule.confidence_baseline,
        priority=rule.priority,
    )


def _cache_key(doc_type: str, client_id: str | None) -> str:
    scope = client_id or "global"
    return f"rules:{doc_type}:{scope}"


async def load_rules(
    doc_type: str,
    client_id: str | None,
    session: AsyncSession,
    redis: Redis,
) -> list[CompiledRule]:
    """
    Carrega regras para (doc_type, client_id) com cache Redis.
    Regras globais + regras do cliente, ordenadas por prioridade.
    """
    cache_key = _cache_key(doc_type, client_id)
    cached = await redis.get(cache_key)

    if cached:
        raw = json.loads(cached)
        return [
            CompiledRule(
                id=r["id"],
                field_name=r["field_name"],
                pattern=re.compile(r["pattern"], re.IGNORECASE | re.DOTALL),
                capture_group=r["capture_group"],
                normalizer=r["normalizer"],
                confidence_baseline=r["confidence_baseline"],
                priority=r["priority"],
            )
            for r in raw
        ]

    # Query: globais + client-specific
    conditions = [
        Rule.doc_type == doc_type,
        Rule.status == RuleStatus.ACTIVE,
    ]
    result = await session.exec(
        select(Rule)
        .where(*conditions)
        .where(
            (Rule.scope == RuleScope.GLOBAL) |
            ((Rule.scope == RuleScope.CLIENT) & (Rule.client_id == client_id))
        )
        .order_by(Rule.priority.asc(), Rule.hit_count.desc())
    )
    rules = result.all()

    compiled = [_compile(r) for r in rules]

    # Serializa para cache usando os SQLModel objects (têm o pattern como string)
    serializable = [
        {
            "id": rule.id,
            "field_name": rule.field_name,
            "pattern": rule.pattern,  # string original do banco
            "capture_group": rule.capture_group,
            "normalizer": rule.normalizer,
            "confidence_baseline": rule.confidence_baseline,
            "priority": rule.priority,
        }
        for rule in rules
    ]
    await redis.setex(cache_key, settings.rule_cache_ttl_seconds, json.dumps(serializable))

    return compiled


async def invalidate_cache(doc_type: str, client_id: str | None, redis: Redis) -> None:
    keys = [_cache_key(doc_type, None), _cache_key(doc_type, client_id)]
    for key in keys:
        await redis.delete(key)
