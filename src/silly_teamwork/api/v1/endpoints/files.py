"""Project and task file HTTP endpoints."""

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse as DownloadResponse

from silly_teamwork.api.dependencies import CurrentUser, DbSession, FileServiceDep
from silly_teamwork.schemas.file import (
    FileIndexItemResponse,
    FileListItemResponse,
    FileMetadataUpdate,
    FileResponse,
    ProjectFileIndexResponse,
)
from silly_teamwork.services.exceptions import (
    FileAccessDeniedError,
    FileNotFoundError,
    FileStorageError,
    FileTooLargeError,
    ProjectNotFoundError,
    TaskNotFoundError,
)

router = APIRouter()
project_router = APIRouter()
task_router = APIRouter()


def _raise_file_http_error(error: Exception) -> NoReturn:
    if isinstance(error, (FileNotFoundError, ProjectNotFoundError, TaskNotFoundError)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, FileAccessDeniedError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    if isinstance(error, FileTooLargeError):
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(error)
        ) from error
    if isinstance(error, FileStorageError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    raise error


@router.get(
    "/index",
    response_model=list[FileIndexItemResponse],
    summary="List all files accessible to the current user",
)
async def list_file_index(
    session: DbSession,
    current_user: CurrentUser,
    file_service: FileServiceDep,
    q: Annotated[str | None, Query(max_length=255)] = None,
    team_id: UUID | None = None,
    project_id: UUID | None = None,
    task_id: UUID | None = None,
) -> list[FileIndexItemResponse]:
    return await file_service.list_file_index(
        session,
        current_user,
        query=q,
        team_id=team_id,
        project_id=project_id,
        task_id=task_id,
    )


@project_router.get(
    "/{project_id}/file-index",
    response_model=ProjectFileIndexResponse,
    summary="List project shared files and task attachments",
    responses={404: {"description": "Project not found or not accessible"}},
)
async def get_project_file_index(
    project_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    file_service: FileServiceDep,
    q: Annotated[str | None, Query(max_length=255)] = None,
) -> ProjectFileIndexResponse:
    try:
        return await file_service.get_project_file_index(
            session, current_user, project_id, query=q
        )
    except Exception as error:
        _raise_file_http_error(error)


@project_router.post(
    "/{project_id}/files",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a project file",
    responses={
        404: {"description": "Project not found or not accessible"},
        413: {"description": "File exceeds MAX_FILE_SIZE"},
    },
)
async def upload_project_file(
    project_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    file_service: FileServiceDep,
    upload: Annotated[UploadFile, File(alias="file", description="File content")],
) -> FileResponse:
    try:
        file = await file_service.upload_project_file(
            session, current_user, project_id, upload
        )
    except Exception as error:
        _raise_file_http_error(error)
    finally:
        await upload.close()
    return FileResponse.model_validate(file)


@task_router.post(
    "/{task_id}/files",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a task file",
    responses={
        404: {"description": "Task not found or not accessible"},
        413: {"description": "File exceeds MAX_FILE_SIZE"},
    },
)
async def upload_task_file(
    task_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    file_service: FileServiceDep,
    upload: Annotated[UploadFile, File(alias="file", description="File content")],
) -> FileResponse:
    try:
        file = await file_service.upload_task_file(session, current_user, task_id, upload)
    except Exception as error:
        _raise_file_http_error(error)
    finally:
        await upload.close()
    return FileResponse.model_validate(file)


@project_router.get(
    "/{project_id}/files",
    response_model=list[FileResponse],
    summary="List project files",
    responses={404: {"description": "Project not found or not accessible"}},
)
async def list_project_files(
    project_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    file_service: FileServiceDep,
) -> list[FileResponse]:
    try:
        files = await file_service.list_project_files(session, current_user, project_id)
    except Exception as error:
        _raise_file_http_error(error)
    return [FileResponse.model_validate(file) for file in files]


@task_router.get(
    "/{task_id}/files",
    response_model=list[FileListItemResponse],
    summary="List task files",
    responses={404: {"description": "Task not found or not accessible"}},
)
async def list_task_files(
    task_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    file_service: FileServiceDep,
) -> list[FileListItemResponse]:
    try:
        task_files = await file_service.list_task_files(session, current_user, task_id)
    except Exception as error:
        _raise_file_http_error(error)
    return task_files


@router.get(
    "/{file_id}/download",
    summary="Download a file",
    response_class=DownloadResponse,
    responses={404: {"description": "File not found or not accessible"}},
)
async def download_file(
    file_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    file_service: FileServiceDep,
) -> DownloadResponse:
    try:
        downloadable = await file_service.get_download(session, current_user, file_id)
    except Exception as error:
        _raise_file_http_error(error)
    return DownloadResponse(
        path=downloadable.path,
        filename=downloadable.file.original_name,
        media_type=downloadable.file.content_type,
    )


@router.patch(
    "/{file_id}",
    response_model=FileResponse,
    summary="Update file metadata",
    responses={
        403: {"description": "File modification permission required"},
        404: {"description": "File not found"},
    },
)
async def update_file_metadata(
    file_id: UUID,
    payload: FileMetadataUpdate,
    session: DbSession,
    current_user: CurrentUser,
    file_service: FileServiceDep,
) -> FileResponse:
    try:
        file = await file_service.update_file_metadata(
            session, current_user, file_id, original_name=payload.original_name
        )
    except Exception as error:
        _raise_file_http_error(error)
    return FileResponse.model_validate(file)


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a file",
    responses={
        403: {"description": "File deletion permission required"},
        404: {"description": "File not found"},
    },
)
async def delete_file(
    file_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    file_service: FileServiceDep,
) -> Response:
    try:
        await file_service.delete_file(session, current_user, file_id)
    except Exception as error:
        _raise_file_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
