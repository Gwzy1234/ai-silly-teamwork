from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from silly_teamwork.api.router import api_router
from silly_teamwork.core.config import get_settings
from silly_teamwork.core.deadline_reminder import run_deadline_reminder_loop
from silly_teamwork.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Own application-wide resources."""
    settings = get_settings()
    stop_event = asyncio.Event()
    reminder_task: asyncio.Task[None] | None = None
    if settings.deadline_reminders_enabled:
        reminder_task = asyncio.create_task(
            run_deadline_reminder_loop(
                stop_event,
                interval_seconds=settings.deadline_reminder_interval_seconds,
                due_soon_hours=settings.deadline_due_soon_hours,
            ),
            name="deadline-reminder-loop",
        )
    try:
        yield
    finally:
        stop_event.set()
        if reminder_task is not None:
            await reminder_task
        await engine.dispose()


def create_app() -> FastAPI:
    """Application factory used by Uvicorn, tests, and future worker processes."""
    settings = get_settings()
    is_production = settings.environment == "production"

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
        lifespan=lifespan,
    )

    if settings.allowed_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()
