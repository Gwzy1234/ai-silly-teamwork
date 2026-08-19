from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.task import Task
from silly_teamwork.repositories import files, tasks
from silly_teamwork.services.file_cleanup import FileCleanupService


class TaskDeletionService:
    """Delete a task and coordinate recoverable cleanup of its physical files."""

    def __init__(self, cleanup_service: FileCleanupService | None = None) -> None:
        self.cleanup = cleanup_service or FileCleanupService()

    async def delete(self, session: AsyncSession, task: Task) -> None:
        task_files = await files.list_task_files(session, task.id)
        cleanup_batch = await self.cleanup.stage(file.storage_key for file in task_files)
        try:
            await tasks.delete(session, task)
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            await self.cleanup.restore(cleanup_batch)
            raise
        await self.cleanup.finish(cleanup_batch)
