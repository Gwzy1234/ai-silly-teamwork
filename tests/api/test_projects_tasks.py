from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
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
)
from silly_teamwork.models.enums import TeamRole
from silly_teamwork.models.team import Team
from silly_teamwork.models.team_member import TeamMember
from silly_teamwork.models.user import User
from silly_teamwork.services.file_cleanup import FileCleanupService
from silly_teamwork.services.files import FileService, get_file_service
from silly_teamwork.services.projects import ProjectService, get_project_service
from silly_teamwork.services.tasks import TaskService, get_task_service
from silly_teamwork.services.teams import TeamService, get_team_service

pytestmark = pytest.mark.asyncio


@dataclass(frozen=True, slots=True)
class ProjectTaskApiContext:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    leader: User
    owner: User
    member: User
    reviewer: User
    outsider: User
    admin: User
    team: Team
    upload_root: Path
    leader_headers: dict[str, str]
    owner_headers: dict[str, str]
    member_headers: dict[str, str]
    outsider_headers: dict[str, str]
    admin_headers: dict[str, str]


@pytest_asyncio.fixture
async def project_task_context(tmp_path: Path) -> AsyncIterator[ProjectTaskApiContext]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with factory.begin() as session:
        leader = User(username="api_leader", password_hash=hash_password("password"))
        owner = User(username="api_owner", password_hash=hash_password("password"))
        member = User(username="api_member", password_hash=hash_password("password"))
        reviewer = User(username="api_reviewer", password_hash=hash_password("password"))
        outsider = User(username="api_outsider", password_hash=hash_password("password"))
        admin = User(username="api_admin", password_hash=hash_password("password"))
        session.add_all([leader, owner, member, reviewer, outsider, admin])
        await session.flush()
        team = Team(name="API Course Team", created_by_id=leader.id)
        session.add(team)
        await session.flush()
        session.add_all(
            [
                TeamMember(team_id=team.id, user_id=leader.id, role=TeamRole.OWNER),
                TeamMember(team_id=team.id, user_id=owner.id, role=TeamRole.MEMBER),
                TeamMember(team_id=team.id, user_id=member.id, role=TeamRole.MEMBER),
                TeamMember(team_id=team.id, user_id=reviewer.id, role=TeamRole.MEMBER),
            ]
        )
        session.add(SystemAdmin(user_id=admin.id, role=SystemAdminRole.SUPER_ADMIN))

    upload_root = tmp_path / "uploads"
    storage = LocalFileStorage(upload_root)
    cleanup = FileCleanupService(storage)
    file_service = FileService(storage=storage, cleanup_service=cleanup)
    project_service = ProjectService(cleanup_service=cleanup)
    task_service = TaskService(cleanup_service=cleanup)
    team_service = TeamService(cleanup_service=cleanup)

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_file_service] = lambda: file_service
    app.dependency_overrides[get_project_service] = lambda: project_service
    app.dependency_overrides[get_task_service] = lambda: task_service
    app.dependency_overrides[get_team_service] = lambda: team_service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield ProjectTaskApiContext(
            client=client,
            session_factory=factory,
            leader=leader,
            owner=owner,
            member=member,
            reviewer=reviewer,
            outsider=outsider,
            admin=admin,
            team=team,
            upload_root=upload_root,
            leader_headers=_headers(leader.id),
            owner_headers=_headers(owner.id),
            member_headers=_headers(member.id),
            outsider_headers=_headers(outsider.id),
            admin_headers=_headers(admin.id),
        )

    app.dependency_overrides.clear()
    await engine.dispose()


def _headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _create_project(context: ProjectTaskApiContext) -> dict[str, object]:
    response = await context.client.post(
        f"/api/v1/teams/{context.team.id}/projects",
        headers=context.leader_headers,
        json={"name": "Final Presentation", "owner_user_id": str(context.owner.id)},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _add_project_member(
    context: ProjectTaskApiContext, project_id: str, user_id: UUID
) -> None:
    response = await context.client.post(
        f"/api/v1/projects/{project_id}/members",
        headers=context.owner_headers,
        json={"user_id": str(user_id)},
    )
    assert response.status_code == 201, response.text


async def _create_task(context: ProjectTaskApiContext, project_id: str) -> dict[str, object]:
    response = await context.client.post(
        f"/api/v1/projects/{project_id}/tasks",
        headers=context.owner_headers,
        json={"title": "Prepare slides", "owner_user_id": str(context.member.id)},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _upload_task_file(
    context: ProjectTaskApiContext, task_id: str, *, content: bytes = b"task file"
) -> tuple[dict[str, object], Path]:
    response = await context.client.post(
        f"/api/v1/tasks/{task_id}/files",
        headers=context.member_headers,
        files={"file": ("task.txt", content, "text/plain")},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    async with context.session_factory() as session:
        file = await session.get(File, UUID(str(payload["id"])))
        assert file is not None
        path = context.upload_root / file.storage_key
    assert path.read_bytes() == content
    return payload, path


async def _upload_project_file(
    context: ProjectTaskApiContext,
    project_id: str,
    *,
    content: bytes = b"project file",
) -> tuple[dict[str, object], Path]:
    response = await context.client.post(
        f"/api/v1/projects/{project_id}/files",
        headers=context.owner_headers,
        files={"file": ("project.txt", content, "text/plain")},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    async with context.session_factory() as session:
        file = await session.get(File, UUID(str(payload["id"])))
        assert file is not None
        path = context.upload_root / file.storage_key
    assert path.read_bytes() == content
    return payload, path


async def test_leader_creates_project_with_owner(
    project_task_context: ProjectTaskApiContext,
) -> None:
    project = await _create_project(project_task_context)
    assert project["name"] == "Final Presentation"
    assert project["status"] == "planning"

    members = await project_task_context.client.get(
        f"/api/v1/projects/{project['id']}/members",
        headers=project_task_context.owner_headers,
    )
    assert members.status_code == 200
    assert [(item["user_id"], item["role"]) for item in members.json()] == [
        (str(project_task_context.owner.id), "owner")
    ]


async def test_member_cannot_create_project(
    project_task_context: ProjectTaskApiContext,
) -> None:
    response = await project_task_context.client.post(
        f"/api/v1/teams/{project_task_context.team.id}/projects",
        headers=project_task_context.member_headers,
        json={"name": "Forbidden Project"},
    )
    assert response.status_code == 403


async def test_owner_updates_project_but_member_cannot(
    project_task_context: ProjectTaskApiContext,
) -> None:
    project = await _create_project(project_task_context)
    project_id = str(project["id"])
    await _add_project_member(project_task_context, project_id, project_task_context.member.id)

    owner_response = await project_task_context.client.patch(
        f"/api/v1/projects/{project_id}",
        headers=project_task_context.owner_headers,
        json={"description": "Owner updated this project"},
    )
    assert owner_response.status_code == 200
    assert owner_response.json()["description"] == "Owner updated this project"

    member_response = await project_task_context.client.patch(
        f"/api/v1/projects/{project_id}",
        headers=project_task_context.member_headers,
        json={"name": "Forbidden"},
    )
    assert member_response.status_code == 403

    status_response = await project_task_context.client.patch(
        f"/api/v1/projects/{project_id}/status",
        headers=project_task_context.owner_headers,
        json={"status": "active"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "active"


async def test_task_creation_status_and_member_management(
    project_task_context: ProjectTaskApiContext,
) -> None:
    project = await _create_project(project_task_context)
    project_id = str(project["id"])
    await _add_project_member(project_task_context, project_id, project_task_context.member.id)
    await _add_project_member(project_task_context, project_id, project_task_context.reviewer.id)
    task = await _create_task(project_task_context, project_id)
    task_id = str(task["id"])

    status_response = await project_task_context.client.patch(
        f"/api/v1/tasks/{task_id}/status",
        headers=project_task_context.member_headers,
        json={"status": "in_progress"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "in_progress"

    add_reviewer = await project_task_context.client.post(
        f"/api/v1/tasks/{task_id}/members",
        headers=project_task_context.owner_headers,
        json={"user_id": str(project_task_context.reviewer.id), "role": "reviewer"},
    )
    assert add_reviewer.status_code == 201
    assert add_reviewer.json()["role"] == "reviewer"

    members = await project_task_context.client.get(
        f"/api/v1/tasks/{task_id}/members",
        headers=project_task_context.owner_headers,
    )
    assert members.status_code == 200
    assert {item["role"] for item in members.json()} == {"owner", "reviewer"}

    remove_reviewer = await project_task_context.client.delete(
        f"/api/v1/tasks/{task_id}/members/{project_task_context.reviewer.id}",
        headers=project_task_context.owner_headers,
    )
    assert remove_reviewer.status_code == 204


async def test_project_and_task_owner_transfer(
    project_task_context: ProjectTaskApiContext,
) -> None:
    project = await _create_project(project_task_context)
    project_id = str(project["id"])
    await _add_project_member(project_task_context, project_id, project_task_context.member.id)
    task = await _create_task(project_task_context, project_id)
    task_id = str(task["id"])

    task_owner_response = await project_task_context.client.put(
        f"/api/v1/tasks/{task_id}/owner",
        headers=project_task_context.owner_headers,
        json={"user_id": str(project_task_context.owner.id)},
    )
    assert task_owner_response.status_code == 200
    assert task_owner_response.json()["role"] == "owner"

    project_owner_response = await project_task_context.client.put(
        f"/api/v1/projects/{project_id}/owner",
        headers=project_task_context.leader_headers,
        json={"user_id": str(project_task_context.member.id)},
    )
    assert project_owner_response.status_code == 200
    assert project_owner_response.json()["user_id"] == str(project_task_context.member.id)

    async with project_task_context.session_factory() as session:
        project_owners = (
            await session.execute(
                select(ProjectMember).where(
                    ProjectMember.project_id == UUID(project_id),
                    ProjectMember.role == ProjectRole.OWNER,
                )
            )
        ).scalars().all()
        task_owners = (
            await session.execute(
                select(TaskMember).where(
                    TaskMember.task_id == UUID(task_id),
                    TaskMember.role == TaskRole.OWNER,
                )
            )
        ).scalars().all()
        assert [item.user_id for item in project_owners] == [project_task_context.member.id]
        assert [item.user_id for item in task_owners] == [project_task_context.owner.id]


async def test_unauthorized_and_inaccessible_resources_return_expected_statuses(
    project_task_context: ProjectTaskApiContext,
) -> None:
    project = await _create_project(project_task_context)
    project_id = str(project["id"])
    task = await _create_task(project_task_context, project_id)

    no_token = await project_task_context.client.get(f"/api/v1/projects/{project_id}")
    assert no_token.status_code == 401

    hidden_project = await project_task_context.client.get(
        f"/api/v1/projects/{project_id}", headers=project_task_context.outsider_headers
    )
    hidden_task = await project_task_context.client.get(
        f"/api/v1/tasks/{task['id']}", headers=project_task_context.outsider_headers
    )
    assert hidden_project.status_code == 404
    assert hidden_task.status_code == 404

    forbidden_update = await project_task_context.client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=project_task_context.outsider_headers,
        json={"title": "Forbidden"},
    )
    assert forbidden_update.status_code == 403


@pytest.mark.parametrize("actor", ["leader", "owner", "admin"])
async def test_authorized_actor_deletes_task_and_its_files(
    project_task_context: ProjectTaskApiContext,
    actor: str,
) -> None:
    context = project_task_context
    project = await _create_project(context)
    project_id = str(project["id"])
    await _add_project_member(context, project_id, context.member.id)
    task = await _create_task(context, project_id)
    task_id = str(task["id"])
    uploaded, stored_path = await _upload_task_file(context, task_id)

    headers = {
        "leader": context.leader_headers,
        "owner": context.owner_headers,
        "admin": context.admin_headers,
    }[actor]
    response = await context.client.delete(
        f"/api/v1/tasks/{task_id}", headers=headers
    )

    assert response.status_code == 204, response.text
    assert not stored_path.exists()
    async with context.session_factory() as session:
        assert await session.get(Task, UUID(task_id)) is None
        assert await session.get(File, UUID(str(uploaded["id"]))) is None
        task_members = (
            await session.execute(
                select(TaskMember).where(TaskMember.task_id == UUID(task_id))
            )
        ).scalars().all()
        assert task_members == []


@pytest.mark.parametrize("actor", ["task_owner", "ordinary_member"])
async def test_task_owner_and_ordinary_member_cannot_delete_task(
    project_task_context: ProjectTaskApiContext,
    actor: str,
) -> None:
    context = project_task_context
    project = await _create_project(context)
    project_id = str(project["id"])
    await _add_project_member(context, project_id, context.member.id)
    await _add_project_member(context, project_id, context.reviewer.id)
    task = await _create_task(context, project_id)
    task_id = str(task["id"])

    headers = (
        context.member_headers if actor == "task_owner" else _headers(context.reviewer.id)
    )
    response = await context.client.delete(
        f"/api/v1/tasks/{task_id}", headers=headers
    )

    assert response.status_code == 403
    async with context.session_factory() as session:
        assert await session.get(Task, UUID(task_id)) is not None


@pytest.mark.parametrize("actor", ["leader", "admin"])
async def test_authorized_actor_permanently_deletes_project_tree(
    project_task_context: ProjectTaskApiContext,
    actor: str,
) -> None:
    context = project_task_context
    project = await _create_project(context)
    project_id = str(project["id"])
    await _add_project_member(context, project_id, context.member.id)
    task = await _create_task(context, project_id)
    task_id = str(task["id"])
    project_file, project_path = await _upload_project_file(context, project_id)
    task_file, task_path = await _upload_task_file(context, task_id)

    headers = context.leader_headers if actor == "leader" else context.admin_headers
    response = await context.client.delete(
        f"/api/v1/projects/{project_id}", headers=headers
    )

    assert response.status_code == 204, response.text
    assert not project_path.exists()
    assert not task_path.exists()
    async with context.session_factory() as session:
        assert await session.get(Project, UUID(project_id)) is None
        assert await session.get(Task, UUID(task_id)) is None
        assert await session.get(File, UUID(str(project_file["id"]))) is None
        assert await session.get(File, UUID(str(task_file["id"]))) is None
        assert (
            await session.execute(
                select(ProjectMember).where(ProjectMember.project_id == UUID(project_id))
            )
        ).scalars().all() == []
        assert (
            await session.execute(
                select(TaskMember).where(TaskMember.task_id == UUID(task_id))
            )
        ).scalars().all() == []


@pytest.mark.parametrize("actor", ["project_owner", "task_owner", "ordinary_member"])
async def test_project_owner_task_owner_and_member_cannot_delete_project(
    project_task_context: ProjectTaskApiContext,
    actor: str,
) -> None:
    context = project_task_context
    project = await _create_project(context)
    project_id = str(project["id"])
    await _add_project_member(context, project_id, context.member.id)
    if actor == "task_owner":
        await _create_task(context, project_id)

    headers = context.owner_headers if actor == "project_owner" else context.member_headers
    response = await context.client.delete(
        f"/api/v1/projects/{project_id}", headers=headers
    )

    assert response.status_code == 403
    async with context.session_factory() as session:
        assert await session.get(Project, UUID(project_id)) is not None


@pytest.mark.parametrize("actor", ["leader", "admin"])
async def test_authorized_actor_permanently_deletes_team_tree(
    project_task_context: ProjectTaskApiContext,
    actor: str,
) -> None:
    context = project_task_context
    project = await _create_project(context)
    project_id = str(project["id"])
    await _add_project_member(context, project_id, context.member.id)
    task = await _create_task(context, project_id)
    task_id = str(task["id"])
    project_file, project_path = await _upload_project_file(context, project_id)
    task_file, task_path = await _upload_task_file(context, task_id)

    headers = context.leader_headers if actor == "leader" else context.admin_headers
    response = await context.client.delete(
        f"/api/v1/teams/{context.team.id}", headers=headers
    )

    assert response.status_code == 204, response.text
    assert not project_path.exists()
    assert not task_path.exists()
    async with context.session_factory() as session:
        assert await session.get(Team, context.team.id) is None
        assert await session.get(Project, UUID(project_id)) is None
        assert await session.get(Task, UUID(task_id)) is None
        assert await session.get(File, UUID(str(project_file["id"]))) is None
        assert await session.get(File, UUID(str(task_file["id"]))) is None
        assert (
            await session.execute(
                select(TeamMember).where(TeamMember.team_id == context.team.id)
            )
        ).scalars().all() == []
        assert (
            await session.execute(
                select(ProjectMember).where(ProjectMember.project_id == UUID(project_id))
            )
        ).scalars().all() == []
        assert (
            await session.execute(
                select(TaskMember).where(TaskMember.task_id == UUID(task_id))
            )
        ).scalars().all() == []


@pytest.mark.parametrize("actor", ["project_owner", "task_owner", "ordinary_member"])
async def test_business_members_cannot_permanently_delete_team(
    project_task_context: ProjectTaskApiContext,
    actor: str,
) -> None:
    context = project_task_context
    project = await _create_project(context)
    project_id = str(project["id"])
    await _add_project_member(context, project_id, context.member.id)
    await _add_project_member(context, project_id, context.reviewer.id)
    if actor == "task_owner":
        await _create_task(context, project_id)

    headers = {
        "project_owner": context.owner_headers,
        "task_owner": context.member_headers,
        "ordinary_member": _headers(context.reviewer.id),
    }[actor]
    response = await context.client.delete(
        f"/api/v1/teams/{context.team.id}", headers=headers
    )

    assert response.status_code == 403
    async with context.session_factory() as session:
        assert await session.get(Team, context.team.id) is not None


async def test_openapi_documents_all_project_task_operations() -> None:
    schema = app.openapi()
    expected_operations = {
        ("post", "/api/v1/teams/{team_id}/projects"),
        ("get", "/api/v1/teams/{team_id}/projects"),
        ("delete", "/api/v1/teams/{team_id}"),
        ("get", "/api/v1/projects/{project_id}"),
        ("patch", "/api/v1/projects/{project_id}"),
        ("delete", "/api/v1/projects/{project_id}"),
        ("patch", "/api/v1/projects/{project_id}/status"),
        ("get", "/api/v1/projects/{project_id}/members"),
        ("post", "/api/v1/projects/{project_id}/members"),
        ("delete", "/api/v1/projects/{project_id}/members/{user_id}"),
        ("put", "/api/v1/projects/{project_id}/owner"),
        ("post", "/api/v1/projects/{project_id}/tasks"),
        ("get", "/api/v1/projects/{project_id}/tasks"),
        ("get", "/api/v1/tasks/{task_id}"),
        ("patch", "/api/v1/tasks/{task_id}"),
        ("delete", "/api/v1/tasks/{task_id}"),
        ("patch", "/api/v1/tasks/{task_id}/status"),
        ("get", "/api/v1/tasks/{task_id}/members"),
        ("post", "/api/v1/tasks/{task_id}/members"),
        ("delete", "/api/v1/tasks/{task_id}/members/{user_id}"),
        ("put", "/api/v1/tasks/{task_id}/owner"),
    }
    for method, path in expected_operations:
        operation = schema["paths"][path][method]
        assert operation["security"] == [{"HTTPBearer": []}]
