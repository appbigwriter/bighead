from dataclasses import dataclass

import asyncpg
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
        conn = await asyncpg.connect(settings.direct_database_url.get_secret_value())
        await conn.execute("select 1")
        await conn.close()
        checks["database"] = "ok"
    except Exception:
        ok = False
        checks["database"] = "unavailable"

    try:
        redis = Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True)
        await redis.ping()
        await redis.aclose()
        checks["redis"] = "ok"
    except Exception:
        ok = False
        checks["redis"] = "unavailable"

    return ReadinessResult(ok=ok, checks=checks)
