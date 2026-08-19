import asyncio

import pytest

from silly_teamwork.core.deadline_reminder import run_deadline_reminder_loop


@pytest.mark.asyncio
async def test_reminder_loop_continues_after_a_failed_check() -> None:
    stop_event = asyncio.Event()
    checked_hours: list[int] = []

    async def check(due_soon_hours: int) -> None:
        checked_hours.append(due_soon_hours)
        if len(checked_hours) == 1:
            raise RuntimeError("temporary database failure")
        stop_event.set()

    await asyncio.wait_for(
        run_deadline_reminder_loop(
            stop_event,
            interval_seconds=0.001,
            due_soon_hours=72,
            check=check,
        ),
        timeout=1,
    )

    assert checked_hours == [72, 72]
