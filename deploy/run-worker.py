"""Bind ARQ's queue connection to the same REDIS_URL used by BigHead jobs."""

import os

from arq import run_worker
from arq.connections import RedisSettings
from bighead_worker.main import WorkerAppSettings


def main() -> None:
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        raise RuntimeError("REDIS_URL is required")
    WorkerAppSettings.redis_settings = RedisSettings.from_dsn(redis_url)
    run_worker(WorkerAppSettings)


if __name__ == "__main__":
    main()
