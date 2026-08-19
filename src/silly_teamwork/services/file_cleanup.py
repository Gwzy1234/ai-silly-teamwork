from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from silly_teamwork.core.config import get_settings
from silly_teamwork.core.file_storage import LocalFileStorage

StagedFile = tuple[Path, Path]


@dataclass(frozen=True, slots=True)
class FileCleanupBatch:
    staged_files: tuple[StagedFile, ...]


class FileCleanupService:
    """Coordinate recoverable physical-file cleanup around a database transaction."""

    def __init__(self, storage: LocalFileStorage | None = None) -> None:
        self.storage = storage or LocalFileStorage(get_settings().upload_dir)

    async def stage(self, storage_keys: Iterable[str]) -> FileCleanupBatch:
        staged_files: list[StagedFile] = []
        try:
            for storage_key in storage_keys:
                staged = await asyncio.to_thread(self.storage.stage_delete, storage_key)
                if staged is not None:
                    staged_files.append(staged)
        except Exception:
            await self.restore(FileCleanupBatch(tuple(staged_files)))
            raise
        return FileCleanupBatch(tuple(staged_files))

    async def restore(self, batch: FileCleanupBatch) -> None:
        for staged in reversed(batch.staged_files):
            await asyncio.to_thread(self.storage.restore_staged_delete, staged)

    async def finish(self, batch: FileCleanupBatch) -> None:
        for staged in batch.staged_files:
            await asyncio.to_thread(self.storage.finish_staged_delete, staged)


def get_file_cleanup_service() -> FileCleanupService:
    return FileCleanupService()
