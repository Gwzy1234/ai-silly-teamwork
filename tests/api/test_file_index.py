from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

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

pytestmark = pytest.mark.asyncio


@dataclass(frozen=True, slots=True)
class FileIndexContext:
    client: AsyncClient
    leader: User
    project_member: User
    task_member: User
    outsider: User
    admin: User
    team: Team
    project: Project
    task: Task
    other_project: Project
    headers: dict[UUID, dict[str, str]]
    file_ids: dict[str, UUID]


@pytest_asyncio.fixture
async def file_index_context() -> AsyncIterator[FileIndexContext]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    now = datetime.now(UTC)
    async with factory.begin() as session:
        leader = User(username="index_leader", password_hash=hash_password("password"))
        project_member = User(
            username="index_project_member", password_hash=hash_password("password")
        )
        task_member = User(
            username="index_task_member", password_hash=hash_password("password")
        )
        outsider = User(username="index_outsider", password_hash=hash_password("password"))
        admin = User(username="index_admin", password_hash=hash_password("password"))
        session.add_all([leader, project_member, task_member, outsider, admin])
        await session.flush()

        team = Team(name="Medical Imaging Team", created_by_id=leader.id)
        other_team = Team(name="Hidden Team", created_by_id=outsider.id)
        session.add_all([team, other_team])
        await session.flush()
        session.add_all(
            [
                TeamMember(team_id=team.id, user_id=leader.id, role=TeamRole.OWNER),
                TeamMember(
                    team_id=team.id, user_id=project_member.id, role=TeamRole.MEMBER
                ),
                TeamMember(team_id=team.id, user_id=task_member.id, role=TeamRole.MEMBER),
                TeamMember(
                    team_id=other_team.id, user_id=outsider.id, role=TeamRole.OWNER
                ),
            ]
        )
        session.add(SystemAdmin(user_id=admin.id, role=SystemAdminRole.SUPER_ADMIN))

        project = Project(
            team_id=team.id,
            name="Medical Imaging",
            created_by_id=leader.id,
        )
        other_project = Project(
            team_id=other_team.id,
            name="Private Subject",
            created_by_id=outsider.id,
        )
        session.add_all([project, other_project])
        await session.flush()
        session.add(
            ProjectMember(
                project_id=project.id,
                user_id=project_member.id,
                role=ProjectRole.MEMBER,
            )
        )
        task = Task(
            project_id=project.id,
            title="MRI Experiment",
            created_by_id=leader.id,
        )
        hidden_task = Task(
            project_id=other_project.id,
            title="Hidden Task",
            created_by_id=outsider.id,
        )
        session.add_all([task, hidden_task])
        await session.flush()
        session.add(
            TaskMember(
                task_id=task.id,
                user_id=task_member.id,
                role=TaskRole.COLLABORATOR,
            )
        )

        records = {
            "shared": File(
                project_id=project.id,
                uploaded_by_id=project_member.id,
                original_name="course-guide.pdf",
                storage_key="index/course-guide.pdf",
                content_type="application/pdf",
                size_bytes=100,
                created_at=now - timedelta(hours=2),
            ),
            "task": File(
                task_id=task.id,
                uploaded_by_id=task_member.id,
                original_name="MRI-results.csv",
                storage_key="index/mri-results.csv",
                content_type="text/csv",
                size_bytes=200,
                created_at=now - timedelta(hours=1),
            ),
            "hidden": File(
                task_id=hidden_task.id,
                uploaded_by_id=outsider.id,
                original_name="hidden.pdf",
                storage_key="index/hidden.pdf",
                content_type="application/pdf",
                size_bytes=300,
                created_at=now,
            ),
        }
        session.add_all(records.values())
        await session.flush()
        file_ids = {name: file.id for name, file in records.items()}

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    actors = [leader, project_member, task_member, outsider, admin]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield FileIndexContext(
            client=client,
            leader=leader,
            project_member=project_member,
            task_member=task_member,
            outsider=outsider,
            admin=admin,
            team=team,
            project=project,
            task=task,
            other_project=other_project,
            headers={actor.id: _headers(actor.id) for actor in actors},
            file_ids=file_ids,
        )

    app.dependency_overrides.clear()
    await engine.dispose()


def _headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def test_global_file_index_filters_by_existing_access_rules_and_time(
    file_index_context: FileIndexContext,
) -> None:
    context = file_index_context
    leader_response = await context.client.get(
        "/api/v1/files/index", headers=context.headers[context.leader.id]
    )
    project_member_response = await context.client.get(
        "/api/v1/files/index", headers=context.headers[context.project_member.id]
    )
    task_member_response = await context.client.get(
        "/api/v1/files/index", headers=context.headers[context.task_member.id]
    )

    assert leader_response.status_code == 200
    assert [item["id"] for item in leader_response.json()] == [
        str(context.file_ids["task"]),
        str(context.file_ids["shared"]),
    ]
    assert [item["id"] for item in project_member_response.json()] == [
        str(context.file_ids["task"]),
        str(context.file_ids["shared"]),
    ]
    assert [item["id"] for item in task_member_response.json()] == [
        str(context.file_ids["task"])
    ]
    assert all(
        item["permissions"] == {"can_modify": True, "can_delete": True}
        for item in leader_response.json()
    )
    project_member_items = {
        item["id"]: item["permissions"] for item in project_member_response.json()
    }
    assert project_member_items[str(context.file_ids["shared"])] == {
        "can_modify": True,
        "can_delete": True,
    }
    assert project_member_items[str(context.file_ids["task"])] == {
        "can_modify": False,
        "can_delete": False,
    }
    assert task_member_response.json()[0]["permissions"] == {
        "can_modify": True,
        "can_delete": True,
    }


async def test_global_file_index_search_and_basic_filters(
    file_index_context: FileIndexContext,
) -> None:
    context = file_index_context
    headers = context.headers[context.leader.id]
    cases = [
        ({"q": "mri"}, "task"),
        ({"team_id": str(context.team.id)}, "task"),
        ({"project_id": str(context.project.id)}, "task"),
        ({"task_id": str(context.task.id)}, "task"),
    ]
    for params, expected in cases:
        response = await context.client.get(
            "/api/v1/files/index", headers=headers, params=params
        )
        assert response.status_code == 200
        assert response.json()[0]["id"] == str(context.file_ids[expected])
    task_filter = await context.client.get(
        "/api/v1/files/index",
        headers=headers,
        params={"task_id": str(context.task.id)},
    )
    assert len(task_filter.json()) == 1


async def test_global_index_hides_files_from_outsider_and_allows_system_admin(
    file_index_context: FileIndexContext,
) -> None:
    context = file_index_context
    admin_response = await context.client.get(
        "/api/v1/files/index", headers=context.headers[context.admin.id]
    )
    outsider_response = await context.client.get(
        "/api/v1/files/index",
        headers=context.headers[context.outsider.id],
        params={"project_id": str(context.project.id)},
    )
    assert admin_response.status_code == 200
    assert {item["id"] for item in admin_response.json()} == {
        str(context.file_ids["shared"]),
        str(context.file_ids["task"]),
        str(context.file_ids["hidden"]),
    }
    assert all(
        item["permissions"] == {"can_modify": True, "can_delete": True}
        for item in admin_response.json()
    )
    assert outsider_response.status_code == 200
    assert outsider_response.json() == []


async def test_system_admin_can_access_any_project_file_index(
    file_index_context: FileIndexContext,
) -> None:
    context = file_index_context
    visible_project = await context.client.get(
        f"/api/v1/projects/{context.project.id}/file-index",
        headers=context.headers[context.admin.id],
    )
    hidden_project = await context.client.get(
        f"/api/v1/projects/{context.other_project.id}/file-index",
        headers=context.headers[context.admin.id],
    )

    assert visible_project.status_code == 200
    assert {item["id"] for group in visible_project.json()["tasks"] for item in group["files"]} == {
        str(context.file_ids["task"])
    }
    assert hidden_project.status_code == 200
    assert {item["id"] for group in hidden_project.json()["tasks"] for item in group["files"]} == {
        str(context.file_ids["hidden"])
    }


async def test_project_file_index_groups_shared_and_task_files(
    file_index_context: FileIndexContext,
) -> None:
    context = file_index_context
    response = await context.client.get(
        f"/api/v1/projects/{context.project.id}/file-index",
        headers=context.headers[context.project_member.id],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["project"] == {
        "id": str(context.project.id),
        "name": "Medical Imaging",
    }
    assert [item["id"] for item in payload["shared_files"]] == [
        str(context.file_ids["shared"])
    ]
    assert payload["tasks"][0]["task"]["title"] == "MRI Experiment"
    assert [item["id"] for item in payload["tasks"][0]["files"]] == [
        str(context.file_ids["task"])
    ]
    assert payload["tasks"][0]["files"][0]["uploader"]["username"] == (
        "index_task_member"
    )
    assert payload["shared_files"][0]["permissions"] == {
        "can_modify": True,
        "can_delete": True,
    }
    assert payload["tasks"][0]["files"][0]["permissions"] == {
        "can_modify": False,
        "can_delete": False,
    }


async def test_project_file_index_rejects_users_without_project_access(
    file_index_context: FileIndexContext,
) -> None:
    context = file_index_context
    task_member_response = await context.client.get(
        f"/api/v1/projects/{context.project.id}/file-index",
        headers=context.headers[context.task_member.id],
    )
    missing_jwt_response = await context.client.get("/api/v1/files/index")
    assert task_member_response.status_code == 404
    assert missing_jwt_response.status_code == 401


async def test_file_index_openapi_paths_are_registered() -> None:
    schema = app.openapi()
    assert "get" in schema["paths"]["/api/v1/files/index"]
    assert "get" in schema["paths"]["/api/v1/projects/{project_id}/file-index"]
