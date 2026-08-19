from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID | None
    task_id: UUID | None
    uploaded_by_id: UUID | None
    original_name: str
    content_type: str
    size_bytes: int
    checksum_sha256: str | None
    created_at: datetime
    updated_at: datetime


class FilePermissionsResponse(BaseModel):
    can_modify: bool
    can_delete: bool


class FileListItemResponse(FileResponse):
    permissions: FilePermissionsResponse


class FileMetadataUpdate(BaseModel):
    original_name: str = Field(min_length=1, max_length=255)

    @field_validator("original_name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("File name must not be blank")
        return value


class FileIndexTeamResponse(BaseModel):
    id: UUID
    name: str


class FileIndexProjectResponse(BaseModel):
    id: UUID
    name: str


class FileIndexTaskResponse(BaseModel):
    id: UUID
    title: str


class FileIndexUploaderResponse(BaseModel):
    id: UUID
    username: str
    nickname: str | None


class FileIndexItemResponse(FileListItemResponse):
    uploaded_at: datetime
    team: FileIndexTeamResponse
    project: FileIndexProjectResponse
    task: FileIndexTaskResponse | None
    uploader: FileIndexUploaderResponse | None


class ProjectFileTaskGroupResponse(BaseModel):
    task: FileIndexTaskResponse
    files: list[FileIndexItemResponse]


class ProjectFileIndexResponse(BaseModel):
    project: FileIndexProjectResponse
    shared_files: list[FileIndexItemResponse]
    tasks: list[ProjectFileTaskGroupResponse]
