from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from silly_teamwork.db.session import AsyncSessionFactory
from silly_teamwork.services.deadlines import DeadlineService

logger = logging.getLogger(__name__)

ReminderCheck = Callable[[int], Awaitable[None]]


async def run_deadline_reminder_check(due_soon_hours: int) -> None:
    """Run one deadline reminder pass in an isolated database session."""
    async with AsyncSessionFactory() as session:
        await DeadlineService().create_task_deadline_notifications(session, due_soon_hours)


async def run_deadline_reminder_loop(
    stop_event: asyncio.Event,
    *,
    interval_seconds: float,
    due_soon_hours: int,
    check: ReminderCheck | None = None,
) -> None:
    """Run reminder checks periodically until application shutdown."""
    execute_check = check or run_deadline_reminder_check
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            try:
                await execute_check(due_soon_hours)
            except Exception:
                logger.exception("Deadline reminder check failed")
