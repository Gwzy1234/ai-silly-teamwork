from __future__ import annotations

import asyncio
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.core.config import get_settings
from silly_teamwork.core.file_storage import LocalFileStorage, sanitize_filename
from silly_teamwork.models.file import File
from silly_teamwork.models.user import User
from silly_teamwork.repositories import files, projects, tasks
from silly_teamwork.schemas.file import (
    FileIndexItemResponse,
    FileIndexProjectResponse,
    FileIndexTaskResponse,
    FileIndexTeamResponse,
    FileIndexUploaderResponse,
    FileListItemResponse,
    FilePermissionsResponse,
    ProjectFileIndexResponse,
    ProjectFileTaskGroupResponse,
)
from silly_teamwork.services.collaboration_access import CollaborationAccessService
from silly_teamwork.services.event_notifications import EventNotificationService
from silly_teamwork.services.exceptions import (
    FileAccessDeniedError,
    FileNotFoundError,
    FileStorageError,
    FileTooLargeError,
    ProjectNotFoundError,
    TaskNotFoundError,
)
from silly_teamwork.services.file_cleanup import FileCleanupService

UPLOAD_CHUNK_SIZE = 1024 * 1024


class UploadedFile(Protocol):
    filename: str | None
    content_type: str | None

    async def read(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True, slots=True)
class DownloadableFile:
    file: File
    path: Path


class FileService:
    def __init__(
        self,
        access_service: CollaborationAccessService | None = None,
        storage: LocalFileStorage | None = None,
        cleanup_service: FileCleanupService | None = None,
        event_notification_service: EventNotificationService | None = None,
        max_file_size: int | None = None,
    ) -> None:
        settings = get_settings()
        self.access = access_service or CollaborationAccessService()
        self.storage = storage or LocalFileStorage(settings.upload_dir)
        self.cleanup = cleanup_service or FileCleanupService(self.storage)
        self.events = event_notification_service or EventNotificationService(self.access)
        self.max_file_size = max_file_size or settings.max_file_size

    async def upload_project_file(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
        upload: UploadedFile,
    ) -> File:
        project = await projects.get_by_id(session, project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")
        if not await self.access.can_upload_project_file(session, current_user, project_id):
            raise ProjectNotFoundError("Project not found")
        original_name = sanitize_filename(upload.filename)
        target = self.storage.project_target(project.team_id, project_id, original_name)
        return await self._persist_upload(
            session,
            current_user,
            upload,
            target.absolute_path,
            target.storage_key,
            original_name,
            project_id=project_id,
        )

    async def upload_task_file(
        self,
        session: AsyncSession,
        current_user: User,
        task_id: UUID,
        upload: UploadedFile,
    ) -> File:
        task = await tasks.get_by_id(session, task_id)
        if task is None:
            raise TaskNotFoundError("Task not found")
        if not await self.access.can_upload_task_file(session, current_user, task_id):
            raise TaskNotFoundError("Task not found")
        project = await projects.get_by_id(session, task.project_id)
        if project is None:
            raise TaskNotFoundError("Task not found")
        original_name = sanitize_filename(upload.filename)
        target = self.storage.task_target(project.team_id, task_id, original_name)
        return await self._persist_upload(
            session,
            current_user,
            upload,
            target.absolute_path,
            target.storage_key,
            original_name,
            task_id=task_id,
        )

    async def list_project_files(
        self, session: AsyncSession, current_user: User, project_id: UUID
    ) -> list[File]:
        await self.access.require_project_file_access(session, current_user, project_id)
        return await files.list_project_files(session, project_id)

    async def list_task_files(
        self, session: AsyncSession, current_user: User, task_id: UUID
    ) -> list[FileListItemResponse]:
        await self.access.require_task_file_access(session, current_user, task_id)
        task_files = await files.list_task_files(session, task_id)
        return [await self._list_item(session, current_user, file) for file in task_files]

    async def list_file_index(
        self,
        session: AsyncSession,
        current_user: User,
        *,
        query: str | None = None,
        team_id: UUID | None = None,
        project_id: UUID | None = None,
        task_id: UUID | None = None,
    ) -> list[FileIndexItemResponse]:
        access_scope = await self.access.get_file_access_scope(session, current_user)
        rows = await files.list_accessible_file_index(
            session,
            can_access_all_files=access_scope.can_access_all_files,
            leader_team_ids=access_scope.leader_team_ids,
            accessible_project_ids=access_scope.project_ids,
            collaborative_task_ids=access_scope.collaborative_task_ids,
            personal_task_ids=access_scope.personal_task_ids,
            query=self._normalize_search(query),
            team_id=team_id,
            project_id=project_id,
            task_id=task_id,
        )
        return [await self._index_item(session, current_user, row) for row in rows]

    async def get_project_file_index(
        self,
        session: AsyncSession,
        current_user: User,
        project_id: UUID,
        *,
        query: str | None = None,
    ) -> ProjectFileIndexResponse:
        project = await self.access.require_project_file_access(session, current_user, project_id)
        access_scope = await self.access.get_file_access_scope(session, current_user)
        rows = await files.list_project_file_index(
            session,
            project_id,
            can_access_all_files=access_scope.can_access_all_files,
            leader_team_ids=access_scope.leader_team_ids,
            accessible_project_ids=access_scope.project_ids,
            collaborative_task_ids=access_scope.collaborative_task_ids,
            personal_task_ids=access_scope.personal_task_ids,
            query=self._normalize_search(query),
        )
        shared_files: list[FileIndexItemResponse] = []
        grouped_tasks: dict[UUID, ProjectFileTaskGroupResponse] = {}
        for row in rows:
            item = await self._index_item(session, current_user, row)
            task = row[2]
            if task is None:
                shared_files.append(item)
                continue
            group = grouped_tasks.get(task.id)
            if group is None:
                group = ProjectFileTaskGroupResponse(
                    task=FileIndexTaskResponse(id=task.id, title=task.title),
                    files=[],
                )
                grouped_tasks[task.id] = group
            group.files.append(item)
        return ProjectFileIndexResponse(
            project=FileIndexProjectResponse(id=project.id, name=project.name),
            shared_files=shared_files,
            tasks=list(grouped_tasks.values()),
        )

    async def get_download(
        self, session: AsyncSession, current_user: User, file_id: UUID
    ) -> DownloadableFile:
        file = await self._require_file(session, file_id)
        await self._require_file_access(session, current_user, file)
        path = self.storage.resolve(file.storage_key)
        if not path.is_file():
            raise FileStorageError("Stored file is missing")
        return DownloadableFile(file=file, path=path)

    async def update_file_metadata(
        self,
        session: AsyncSession,
        current_user: User,
        file_id: UUID,
        *,
        original_name: str,
    ) -> File:
        file = await self._require_file(session, file_id)
        if not await self.access.can_modify_file(session, current_user, file_id):
            raise FileAccessDeniedError("File modification permission required")
        safe_name = sanitize_filename(original_name)
        try:
            files.update_file_metadata(file, original_name=safe_name)
            await session.flush()
            await session.commit()
            await session.refresh(file)
        except Exception:
            await session.rollback()
            raise
        return file

    async def delete_file(self, session: AsyncSession, current_user: User, file_id: UUID) -> None:
        file = await self._require_file(session, file_id)
        if not await self.access.can_delete_file(session, current_user, file_id):
            raise FileAccessDeniedError("File deletion permission required")
        cleanup_batch = await self.cleanup.stage([file.storage_key])
        try:
            await files.delete_file(session, file)
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            await self.cleanup.restore(cleanup_batch)
            raise
        await self.cleanup.finish(cleanup_batch)

    async def _persist_upload(
        self,
        session: AsyncSession,
        current_user: User,
        upload: UploadedFile,
        absolute_path: Path,
        storage_key: str,
        original_name: str,
        *,
        project_id: UUID | None = None,
        task_id: UUID | None = None,
    ) -> File:
        size, checksum = await self._write_upload(upload, absolute_path)
        file = File(
            project_id=project_id,
            task_id=task_id,
            uploaded_by_id=current_user.id,
            original_name=original_name,
            storage_key=storage_key,
            content_type=(upload.content_type or "application/octet-stream")[:255],
            size_bytes=size,
            checksum_sha256=checksum,
        )
        try:
            files.create_file(session, file)
            await session.flush()
            await self.events.notify_file_uploaded(session, current_user, file)
            await session.commit()
            await session.refresh(file)
        except Exception:
            await session.rollback()
            await asyncio.to_thread(absolute_path.unlink, missing_ok=True)
            raise
        return file

    async def _write_upload(self, upload: UploadedFile, destination: Path) -> tuple[int, str]:
        total = 0
        digest = sha256()
        try:
            with destination.open("xb") as output:
                while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                    total += len(chunk)
                    if total > self.max_file_size:
                        raise FileTooLargeError(
                            f"File exceeds the {self.max_file_size}-byte size limit"
                        )
                    digest.update(chunk)
                    await asyncio.to_thread(output.write, chunk)
        except Exception:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise
        return total, digest.hexdigest()

    @staticmethod
    async def _require_file(session: AsyncSession, file_id: UUID) -> File:
        file = await files.get_file(session, file_id)
        if file is None:
            raise FileNotFoundError("File not found")
        return file

    async def _require_file_access(
        self, session: AsyncSession, current_user: User, file: File
    ) -> None:
        await self.access.require_file_access(session, current_user, file)

    @staticmethod
    def _normalize_search(query: str | None) -> str | None:
        if query is None:
            return None
        return query.strip() or None

    async def _permissions(
        self, session: AsyncSession, current_user: User, file_id: UUID
    ) -> FilePermissionsResponse:
        can_modify = await self.access.can_modify_file(session, current_user, file_id)
        can_delete = await self.access.can_delete_file(session, current_user, file_id)
        return FilePermissionsResponse(
            can_modify=can_modify,
            can_delete=can_delete,
        )

    async def _list_item(
        self, session: AsyncSession, current_user: User, file: File
    ) -> FileListItemResponse:
        return FileListItemResponse(
            id=file.id,
            project_id=file.project_id,
            task_id=file.task_id,
            uploaded_by_id=file.uploaded_by_id,
            original_name=file.original_name,
            content_type=file.content_type,
            size_bytes=file.size_bytes,
            checksum_sha256=file.checksum_sha256,
            created_at=file.created_at,
            updated_at=file.updated_at,
            permissions=await self._permissions(session, current_user, file.id),
        )

    async def _index_item(
        self,
        session: AsyncSession,
        current_user: User,
        row: files.FileIndexRow,
    ) -> FileIndexItemResponse:
        file, project, task, team, uploader = row
        return FileIndexItemResponse(
            id=file.id,
            project_id=file.project_id,
            task_id=file.task_id,
            uploaded_by_id=file.uploaded_by_id,
            original_name=file.original_name,
            content_type=file.content_type,
            size_bytes=file.size_bytes,
            checksum_sha256=file.checksum_sha256,
            created_at=file.created_at,
            updated_at=file.updated_at,
            permissions=await self._permissions(session, current_user, file.id),
            uploaded_at=file.created_at,
            team=FileIndexTeamResponse(id=team.id, name=team.name),
            project=FileIndexProjectResponse(id=project.id, name=project.name),
            task=None if task is None else FileIndexTaskResponse(id=task.id, title=task.title),
            uploader=None
            if uploader is None
            else FileIndexUploaderResponse(
                id=uploader.id,
                username=uploader.username,
                nickname=uploader.display_name,
            ),
        )


def get_file_service() -> FileService:
    return FileService()
