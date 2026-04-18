from __future__ import annotations

import asyncio
import logging
import os

from redis.asyncio import Redis

from app.core.logging import configure_logging

LOGGER = logging.getLogger("attendance.worker")


async def run_worker() -> None:
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), encoding="utf-8", decode_responses=True)
    LOGGER.info("worker_started")
    try:
        while True:
            item = await redis.brpop("attendance:jobs", timeout=5)
            if item is None:
                await asyncio.sleep(0.2)
                continue
            _, payload = item
            LOGGER.info("job_received", extra={"payload": payload})
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run_worker())

