import asyncio
from dataclasses import dataclass

import asyncpg  # type: ignore[import-untyped]
from redis.asyncio import Redis

from bighead_api.config import Settings


@dataclass(slots=True)
class ReadinessResult:
    ok: bool
    checks: dict[str, str]


async def run_readiness_checks(settings: Settings) -> ReadinessResult:
    checks: dict[str, str] = {}
    ok = True

    try:
        async with asyncio.timeout(3):
            conn = await asyncpg.connect(settings.database_url.get_secret_value())
            try:
                await conn.execute("select 1")
            finally:
                await conn.close()
        checks["database"] = "ok"
    except Exception:
        ok = False
        checks["database"] = "unavailable"

    try:
        async with asyncio.timeout(3):
            redis = Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True)
            try:
                await redis.ping()
            finally:
                await redis.aclose()
        checks["redis"] = "ok"
    except Exception:
        ok = False
        checks["redis"] = "unavailable"

    return ReadinessResult(ok=ok, checks=checks)
