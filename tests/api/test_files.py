from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from silly_teamwork.core.file_storage import LocalFileStorage
from silly_teamwork.core.security import create_access_token, hash_password
from silly_teamwork.db.base import Base
from silly_teamwork.db.session import get_db_session
from silly_teamwork.main import app
from silly_teamwork.models import (
    File,
    Project,
    ProjectMember,
    ProjectRole,
    SystemAdmin,
    SystemAdminRole,
    Task,
    TaskMember,
    TaskRole,
    Team,
    TeamMember,
    TeamRole,
    User,
)
from silly_teamwork.services.files import FileService, get_file_service

pytestmark = pytest.mark.asyncio


@dataclass(frozen=True, slots=True)
class FileApiContext:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    upload_root: Path
    leader: User
    owner: User
    member: User
    task_member: User
    outsider: User
    admin: User
    project: Project
    task: Task
    headers: dict[UUID, dict[str, str]]


@pytest_asyncio.fixture
async def file_context(tmp_path: Path) -> AsyncIterator[FileApiContext]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with factory.begin() as session:
        leader = User(username="file_leader", password_hash=hash_password("password"))
        owner = User(username="file_owner", password_hash=hash_password("password"))
        member = User(username="file_member", password_hash=hash_password("password"))
        task_member = User(
            username="file_task_member", password_hash=hash_password("password")
        )
        outsider = User(username="file_outsider", password_hash=hash_password("password"))
        admin = User(username="file_admin", password_hash=hash_password("password"))
        session.add_all([leader, owner, member, task_member, outsider, admin])
        await session.flush()
        team = Team(name="File API Team", created_by_id=leader.id)
        session.add(team)
        await session.flush()
        session.add_all(
            [
                TeamMember(team_id=team.id, user_id=leader.id, role=TeamRole.OWNER),
                TeamMember(team_id=team.id, user_id=owner.id, role=TeamRole.MEMBER),
                TeamMember(team_id=team.id, user_id=member.id, role=TeamRole.MEMBER),
                TeamMember(team_id=team.id, user_id=task_member.id, role=TeamRole.MEMBER),
            ]
        )
        session.add(SystemAdmin(user_id=admin.id, role=SystemAdminRole.SUPER_ADMIN))
        project = Project(team_id=team.id, name="File Project", created_by_id=leader.id)
        session.add(project)
        await session.flush()
        session.add_all(
            [
                ProjectMember(
                    project_id=project.id, user_id=owner.id, role=ProjectRole.OWNER
                ),
                ProjectMember(
                    project_id=project.id, user_id=member.id, role=ProjectRole.MEMBER
                ),
            ]
        )
        task = Task(project_id=project.id, title="File Task", created_by_id=owner.id)
        session.add(task)
        await session.flush()
        session.add(
            TaskMember(
                task_id=task.id, user_id=task_member.id, role=TaskRole.COLLABORATOR
            )
        )

    upload_root = tmp_path / "uploads"
    file_service = FileService(
        storage=LocalFileStorage(upload_root), max_file_size=1024 * 1024
    )

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_file_service] = lambda: file_service
    users = [leader, owner, member, task_member, outsider, admin]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield FileApiContext(
            client=client,
            session_factory=factory,
            upload_root=upload_root,
            leader=leader,
            owner=owner,
            member=member,
            task_member=task_member,
            outsider=outsider,
            admin=admin,
            project=project,
            task=task,
            headers={user.id: _headers(user.id) for user in users},
        )

    app.dependency_overrides.clear()
    await engine.dispose()


def _headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _upload_project_file(
    context: FileApiContext,
    user: User,
    *,
    filename: str = "notes.txt",
    content: bytes = b"project notes",
) -> dict[str, object]:
    response = await context.client.post(
        f"/api/v1/projects/{context.project.id}/files",
        headers=context.headers[user.id],
        files={"file": (filename, content, "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _upload_task_file(
    context: FileApiContext, user: User, *, content: bytes = b"task attachment"
) -> dict[str, object]:
    response = await context.client.post(
        f"/api/v1/tasks/{context.task.id}/files",
        headers=context.headers[user.id],
        files={"file": ("task.txt", content, "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_project_member_uploads_with_safe_random_path(
    file_context: FileApiContext,
) -> None:
    response = await _upload_project_file(
        file_context, file_context.member, filename="../../test.txt"
    )
    assert response["original_name"] == "test.txt"
    assert "storage_key" not in response
    assert response["size_bytes"] == len(b"project notes")

    async with file_context.session_factory() as session:
        file = await session.get(File, UUID(str(response["id"])))
        assert file is not None
        expected_prefix = (
            f"teams/{file_context.project.team_id}/projects/"
            f"{file_context.project.id}/files/"
        )
        assert file.storage_key.startswith(expected_prefix)
        assert ".." not in file.storage_key
        stored_path = (file_context.upload_root / file.storage_key).resolve()
        assert stored_path.is_relative_to(file_context.upload_root.resolve())
        assert stored_path.read_bytes() == b"project notes"


async def test_task_member_uploads_and_lists_task_files(
    file_context: FileApiContext,
) -> None:
    uploaded = await _upload_task_file(file_context, file_context.task_member)
    response = await file_context.client.get(
        f"/api/v1/tasks/{file_context.task.id}/files",
        headers=file_context.headers[file_context.task_member.id],
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [uploaded["id"]]
    assert response.json()[0]["permissions"] == {
        "can_modify": True,
        "can_delete": True,
    }

    member_response = await file_context.client.get(
        f"/api/v1/tasks/{file_context.task.id}/files",
        headers=file_context.headers[file_context.member.id],
    )
    assert member_response.status_code == 200
    assert member_response.json()[0]["permissions"] == {
        "can_modify": False,
        "can_delete": False,
    }


async def test_outsider_cannot_upload(file_context: FileApiContext) -> None:
    project_response = await file_context.client.post(
        f"/api/v1/projects/{file_context.project.id}/files",
        headers=file_context.headers[file_context.outsider.id],
        files={"file": ("forbidden.txt", b"no", "text/plain")},
    )
    task_response = await file_context.client.post(
        f"/api/v1/tasks/{file_context.task.id}/files",
        headers=file_context.headers[file_context.outsider.id],
        files={"file": ("forbidden.txt", b"no", "text/plain")},
    )
    assert project_response.status_code == 404
    assert task_response.status_code == 404
    assert not list(file_context.upload_root.rglob("forbidden.txt"))


async def test_member_can_download_accessible_file(file_context: FileApiContext) -> None:
    content = b"downloadable content"
    uploaded = await _upload_project_file(file_context, file_context.owner, content=content)
    response = await file_context.client.get(
        f"/api/v1/files/{uploaded['id']}/download",
        headers=file_context.headers[file_context.member.id],
    )
    assert response.status_code == 200
    assert response.content == content
    assert 'filename="notes.txt"' in response.headers["content-disposition"]


async def test_uploader_deletes_own_file(file_context: FileApiContext) -> None:
    uploaded = await _upload_project_file(file_context, file_context.member)
    async with file_context.session_factory() as session:
        file = await session.get(File, UUID(str(uploaded["id"])))
        assert file is not None
        stored_path = file_context.upload_root / file.storage_key

    response = await file_context.client.delete(
        f"/api/v1/files/{uploaded['id']}",
        headers=file_context.headers[file_context.member.id],
    )
    assert response.status_code == 204
    assert not stored_path.exists()
    async with file_context.session_factory() as session:
        assert await session.get(File, UUID(str(uploaded["id"]))) is None


async def test_member_cannot_delete_another_users_file(
    file_context: FileApiContext,
) -> None:
    uploaded = await _upload_project_file(file_context, file_context.owner)
    response = await file_context.client.delete(
        f"/api/v1/files/{uploaded['id']}",
        headers=file_context.headers[file_context.member.id],
    )
    assert response.status_code == 403


@pytest.mark.parametrize("actor_name", ["owner", "leader"])
async def test_project_owner_and_team_leader_can_delete_file(
    file_context: FileApiContext, actor_name: str
) -> None:
    uploaded = await _upload_project_file(file_context, file_context.member)
    actor = getattr(file_context, actor_name)
    response = await file_context.client.delete(
        f"/api/v1/files/{uploaded['id']}", headers=file_context.headers[actor.id]
    )
    assert response.status_code == 204


async def test_super_admin_can_modify_and_delete_any_file(
    file_context: FileApiContext,
) -> None:
    uploaded = await _upload_task_file(file_context, file_context.task_member)
    list_response = await file_context.client.get(
        f"/api/v1/tasks/{file_context.task.id}/files",
        headers=file_context.headers[file_context.admin.id],
    )
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [uploaded["id"]]

    download_response = await file_context.client.get(
        f"/api/v1/files/{uploaded['id']}/download",
        headers=file_context.headers[file_context.admin.id],
    )
    assert download_response.status_code == 200
    assert download_response.content == b"task attachment"

    patch_response = await file_context.client.patch(
        f"/api/v1/files/{uploaded['id']}",
        headers=file_context.headers[file_context.admin.id],
        json={"original_name": "admin-renamed.txt"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["original_name"] == "admin-renamed.txt"

    delete_response = await file_context.client.delete(
        f"/api/v1/files/{uploaded['id']}",
        headers=file_context.headers[file_context.admin.id],
    )
    assert delete_response.status_code == 204


async def test_upload_size_limit_removes_partial_file(
    file_context: FileApiContext,
) -> None:
    oversized = b"x" * (1024 * 1024 + 1)
    response = await file_context.client.post(
        f"/api/v1/projects/{file_context.project.id}/files",
        headers=file_context.headers[file_context.member.id],
        files={"file": ("large.bin", oversized, "application/octet-stream")},
    )
    assert response.status_code == 413
    assert list(file_context.upload_root.rglob("*")) == [] or not any(
        path.is_file() for path in file_context.upload_root.rglob("*")
    )


async def test_file_openapi_documents_all_operations() -> None:
    schema = app.openapi()
    expected = {
        ("post", "/api/v1/projects/{project_id}/files"),
        ("get", "/api/v1/projects/{project_id}/files"),
        ("post", "/api/v1/tasks/{task_id}/files"),
        ("get", "/api/v1/tasks/{task_id}/files"),
        ("get", "/api/v1/files/{file_id}/download"),
        ("patch", "/api/v1/files/{file_id}"),
        ("delete", "/api/v1/files/{file_id}"),
    }
    for method, path in expected:
        assert schema["paths"][path][method]["security"] == [{"HTTPBearer": []}]
