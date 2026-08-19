from __future__ import annotations

import asyncio
import logging
import signal

from silly_teamwork.core.config import get_settings
from silly_teamwork.db.session import AsyncSessionFactory, engine
from silly_teamwork.scheduler.service import NotificationScheduler

logger = logging.getLogger(__name__)


async def run_scheduler() -> None:
    settings = get_settings()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for stop_signal in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(stop_signal, stop_event.set)

    scheduler = NotificationScheduler(
        AsyncSessionFactory,
        batch_size=settings.notification_scheduler_batch_size,
        lease_seconds=settings.notification_scheduler_lease_seconds,
        max_attempts=settings.notification_scheduler_max_attempts,
    )
    logger.info("Notification scheduler started")
    try:
        while not stop_event.is_set():
            try:
                result = await scheduler.run_once()
                if result.claimed:
                    logger.info("Notification scheduler run completed: %s", result)
            except Exception:
                logger.exception("Notification scheduler run failed")
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=settings.notification_scheduler_interval_seconds,
                )
            except TimeoutError:
                pass
    finally:
        await engine.dispose()
        logger.info("Notification scheduler stopped")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
