from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentor.durable.models import IdempotencyKey


def derive_effect_key(provider: str, action: str, payload: dict[str, Any]) -> str:
    """Generate a stable idempotency key for a side effect."""
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = sha256(normalized.encode("utf-8")).hexdigest()[:24]
    return f"{provider}:{action}:{digest}"


async def execute_once(
    session_factory: async_sessionmaker[AsyncSession],
    effect_key: str,
    fn: Callable[[], Awaitable[Any]],
    ttl: Optional[timedelta] = timedelta(days=30),
) -> tuple[bool, Any]:
    """
    Execute a side-effecting function once using the idempotency cache.

    Returns (from_cache, result). If the key exists and is not expired,
    skips execution and returns (True, None).
    """
    now = datetime.now(timezone.utc)
    expires_at = now + ttl if ttl else None

    async with session_factory() as session:
        cached = await session.get(IdempotencyKey, effect_key)
        if cached and (cached.expires_at is None or cached.expires_at > now):
            return True, None

    try:
        result = await fn()
    except Exception:
        # Do not record key on failure; allow retry.
        raise

    try:
        async with session_factory() as session:
            session.add(
                IdempotencyKey(
                    effect_key=effect_key,
                    effect_hash=None,
                    expires_at=expires_at,
                )
            )
            await session.commit()
    except IntegrityError:
        # Another worker inserted the key; treat as cached.
        return True, result

    return False, result
