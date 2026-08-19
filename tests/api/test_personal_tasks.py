from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

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
    TaskAssignment,
    TaskMember,
    TaskStatus,
    TaskType,
    Team,
    TeamMember,
    TeamRole,
    User,
)
from silly_teamwork.services.file_cleanup import FileCleanupService
from silly_teamwork.services.files import FileService, get_file_service
from silly_teamwork.services.personal_tasks import (
    PersonalTaskService,
    get_personal_task_service,
)

pytestmark = pytest.mark.asyncio


@dataclass(frozen=True, slots=True)
class PersonalTaskApiContext:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    user_ids: dict[str, UUID]
    headers: dict[str, dict[str, str]]
    team_id: UUID
    project_id: UUID
    second_team_id: UUID
    second_project_id: UUID
    upload_root: Path


@pytest_asyncio.fixture
async def personal_task_api_context(
    tmp_path: Path,
) -> AsyncIterator[PersonalTaskApiContext]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'personal-task-api.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory.begin() as session:
        users = {
            name: User(
                username=f"api-{name}",
                display_name=f"{name.title()} User",
                password_hash=hash_password("password"),
            )
            for name in (
                "leader",
                "team_admin",
                "project_owner",
                "member_one",
                "member_two",
                "unassigned",
                "outsider",
                "super_admin",
            )
        }
        session.add_all(users.values())
        await session.flush()

        team = Team(name="Personal API Team", created_by_id=users["leader"].id)
        second_team = Team(name="Second Personal API Team", created_by_id=users["leader"].id)
        session.add_all([team, second_team])
        await session.flush()
        session.add_all(
            [
                TeamMember(
                    team_id=team.id,
                    user_id=users["leader"].id,
                    role=TeamRole.OWNER,
                ),
                TeamMember(
                    team_id=team.id,
                    user_id=users["team_admin"].id,
                    role=TeamRole.ADMIN,
                ),
                TeamMember(
                    team_id=team.id,
                    user_id=users["project_owner"].id,
                    role=TeamRole.MEMBER,
                ),
                TeamMember(
                    team_id=team.id,
                    user_id=users["member_one"].id,
                    role=TeamRole.MEMBER,
                ),
                TeamMember(
                    team_id=team.id,
                    user_id=users["member_two"].id,
                    role=TeamRole.MEMBER,
                ),
                TeamMember(
                    team_id=team.id,
                    user_id=users["unassigned"].id,
                    role=TeamRole.MEMBER,
                ),
                TeamMember(
                    team_id=second_team.id,
                    user_id=users["leader"].id,
                    role=TeamRole.OWNER,
                ),
                TeamMember(
                    team_id=second_team.id,
                    user_id=users["member_one"].id,
                    role=TeamRole.MEMBER,
                ),
            ]
        )
        session.add(
            SystemAdmin(
                user_id=users["super_admin"].id,
                role=SystemAdminRole.SUPER_ADMIN,
            )
        )

        project = Project(
            team_id=team.id,
            name="Personal API Subject",
            created_by_id=users["leader"].id,
        )
        second_project = Project(
            team_id=second_team.id,
            name="Second Personal API Subject",
            created_by_id=users["leader"].id,
        )
        session.add_all([project, second_project])
        await session.flush()
        session.add(
            ProjectMember(
                project_id=project.id,
                user_id=users["project_owner"].id,
                role=ProjectRole.OWNER,
            )
        )

        user_ids = {name: user.id for name, user in users.items()}
        team_id = team.id
        project_id = project.id
        second_team_id = second_team.id
        second_project_id = second_project.id

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_db_session
    upload_root = tmp_path / "uploads"
    storage = LocalFileStorage(upload_root)
    app.dependency_overrides[get_file_service] = lambda: FileService(
        storage=storage,
        max_file_size=1024 * 1024,
    )
    app.dependency_overrides[get_personal_task_service] = lambda: PersonalTaskService(
        cleanup_service=FileCleanupService(storage)
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield PersonalTaskApiContext(
            client=client,
            session_factory=factory,
            user_ids=user_ids,
            headers={name: _headers(user_id) for name, user_id in user_ids.items()},
            team_id=team_id,
            project_id=project_id,
            second_team_id=second_team_id,
            second_project_id=second_project_id,
            upload_root=upload_root,
        )

    app.dependency_overrides.clear()
    await engine.dispose()


def _headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


def _create_payload(
    context: PersonalTaskApiContext,
    *,
    title: str = "Complete individual report",
    assignee_names: tuple[str, ...] = ("member_one", "member_two"),
    due_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "title": title,
        "description": "Complete this independently",
        "priority": "high",
        "due_at": due_at.isoformat() if due_at is not None else None,
        "assignee_user_ids": [str(context.user_ids[name]) for name in assignee_names],
        "attachment_mode": "shared",
    }


async def _create_personal_task(
    context: PersonalTaskApiContext,
    *,
    actor: str = "leader",
    project_id: UUID | None = None,
    title: str = "Complete individual report",
    assignee_names: tuple[str, ...] = ("member_one", "member_two"),
    due_at: datetime | None = None,
) -> dict[str, object]:
    response = await context.client.post(
        f"/api/v1/projects/{project_id or context.project_id}/personal-tasks",
        headers=context.headers[actor],
        json=_create_payload(
            context,
            title=title,
            assignee_names=assignee_names,
            due_at=due_at,
        ),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _upload_personal_task_file(
    context: PersonalTaskApiContext,
    task_id: str,
    actor: str,
    *,
    filename: str = "personal-shared.txt",
    content: bytes = b"shared personal task file",
) -> dict[str, object]:
    response = await context.client.post(
        f"/api/v1/tasks/{task_id}/files",
        headers=context.headers[actor],
        files={"file": (filename, content, "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("actor", ["leader", "super_admin"])
async def test_authorized_users_create_personal_task_with_assignments(
    personal_task_api_context: PersonalTaskApiContext,
    actor: str,
) -> None:
    context = personal_task_api_context
    response = await context.client.post(
        f"/api/v1/projects/{context.project_id}/personal-tasks",
        headers=context.headers[actor],
        json=_create_payload(context),
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["task"]["task_type"] == "personal"
    assert payload["task"]["attachment_mode"] == "shared"
    assert payload["task"]["project"]["team"]["id"] == str(context.team_id)
    assert {item["user_id"] for item in payload["assignments"]} == {
        str(context.user_ids["member_one"]),
        str(context.user_ids["member_two"]),
    }
    assert {item["status"] for item in payload["assignments"]} == {"todo"}

    task_id = UUID(payload["task"]["id"])
    async with context.session_factory() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(TaskMember).where(TaskMember.task_id == task_id)
            )
            == 0
        )


@pytest.mark.parametrize("actor", ["team_admin", "project_owner", "member_one"])
async def test_disallowed_roles_cannot_create_personal_task(
    personal_task_api_context: PersonalTaskApiContext,
    actor: str,
) -> None:
    context = personal_task_api_context
    response = await context.client.post(
        f"/api/v1/projects/{context.project_id}/personal-tasks",
        headers=context.headers[actor],
        json=_create_payload(context),
    )
    assert response.status_code == 403


async def test_personal_task_create_validation_and_authentication(
    personal_task_api_context: PersonalTaskApiContext,
) -> None:
    context = personal_task_api_context
    endpoint = f"/api/v1/projects/{context.project_id}/personal-tasks"

    no_token = await context.client.post(endpoint, json=_create_payload(context))
    assert no_token.status_code == 401

    invalid_payloads = [
        {**_create_payload(context), "assignee_user_ids": []},
        {
            **_create_payload(context),
            "assignee_user_ids": [str(context.user_ids["outsider"])],
        },
        {**_create_payload(context), "attachment_mode": "individual"},
    ]
    for payload in invalid_payloads:
        response = await context.client.post(
            endpoint, headers=context.headers["leader"], json=payload
        )
        assert response.status_code == 400, response.text

    invalid_shape = await context.client.post(
        endpoint,
        headers=context.headers["leader"],
        json={**_create_payload(context), "title": ""},
    )
    assert invalid_shape.status_code == 422


async def test_my_tasks_are_isolated_filtered_paginated_and_sorted(
    personal_task_api_context: PersonalTaskApiContext,
) -> None:
    context = personal_task_api_context
    now = datetime.now(UTC)
    first = await _create_personal_task(context, title="Due first", due_at=now + timedelta(hours=3))
    second = await _create_personal_task(
        context, title="Due second", due_at=now + timedelta(hours=8)
    )
    no_due = await _create_personal_task(context, title="No deadline")
    done = await _create_personal_task(context, title="Done first", due_at=now + timedelta(hours=1))
    await _create_personal_task(
        context,
        project_id=context.second_project_id,
        title="Second team task",
        assignee_names=("member_one",),
        due_at=now + timedelta(hours=2),
    )

    done_assignment = next(
        item
        for item in done["assignments"]  # type: ignore[union-attr]
        if item["user_id"] == str(context.user_ids["member_one"])
    )
    for target in ("in_progress", "done"):
        response = await context.client.patch(
            f"/api/v1/task-assignments/{done_assignment['id']}/status",
            headers=context.headers["member_one"],
            json={"status": target},
        )
        assert response.status_code == 200, response.text

    response = await context.client.get("/api/v1/tasks/my", headers=context.headers["member_one"])
    assert response.status_code == 200, response.text
    titles = [item["task"]["title"] for item in response.json()]
    assert titles == [
        "Second team task",
        "Due first",
        "Due second",
        "No deadline",
        "Done first",
    ]
    assert "Complete individual report" not in titles

    filtered = await context.client.get(
        "/api/v1/tasks/my",
        headers=context.headers["member_one"],
        params={
            "status": "todo",
            "team_id": str(context.team_id),
            "project_id": str(context.project_id),
            "due_after": (now + timedelta(hours=2)).isoformat(),
            "due_before": (now + timedelta(hours=9)).isoformat(),
        },
    )
    assert filtered.status_code == 200, filtered.text
    assert [item["task"]["id"] for item in filtered.json()] == [
        first["task"]["id"],  # type: ignore[index]
        second["task"]["id"],  # type: ignore[index]
    ]

    page = await context.client.get(
        "/api/v1/tasks/my",
        headers=context.headers["member_one"],
        params={"limit": 1, "offset": 1},
    )
    assert page.status_code == 200
    assert [item["task"]["title"] for item in page.json()] == ["Due first"]

    other_user = await context.client.get("/api/v1/tasks/my", headers=context.headers["unassigned"])
    assert other_user.status_code == 200
    assert other_user.json() == []
    assert no_due["task"]["title"] == "No deadline"  # type: ignore[index]


async def test_personal_task_detail_visibility_and_progress_permissions(
    personal_task_api_context: PersonalTaskApiContext,
) -> None:
    context = personal_task_api_context
    created = await _create_personal_task(context)
    task_id = created["task"]["id"]  # type: ignore[index]

    for actor in ("member_one", "leader", "super_admin"):
        response = await context.client.get(
            f"/api/v1/personal-tasks/{task_id}", headers=context.headers[actor]
        )
        assert response.status_code == 200, response.text
        assert (response.json()["my_assignment"] is not None) is (actor == "member_one")

    for actor in ("unassigned", "team_admin", "project_owner"):
        hidden = await context.client.get(
            f"/api/v1/personal-tasks/{task_id}", headers=context.headers[actor]
        )
        assert hidden.status_code == 404

    no_token = await context.client.get(f"/api/v1/personal-tasks/{task_id}")
    assert no_token.status_code == 401

    for actor in ("leader", "super_admin"):
        response = await context.client.get(
            f"/api/v1/personal-tasks/{task_id}/assignments",
            headers=context.headers[actor],
        )
        assert response.status_code == 200
        assert {item["user"]["nickname"] for item in response.json()} == {
            "Member_One User",
            "Member_Two User",
        }

    forbidden = await context.client.get(
        f"/api/v1/personal-tasks/{task_id}/assignments",
        headers=context.headers["member_one"],
    )
    assert forbidden.status_code == 403


async def test_assignment_detail_and_status_are_owner_scoped(
    personal_task_api_context: PersonalTaskApiContext,
) -> None:
    context = personal_task_api_context
    created = await _create_personal_task(context)
    assignment = next(
        item
        for item in created["assignments"]  # type: ignore[union-attr]
        if item["user_id"] == str(context.user_ids["member_one"])
    )
    assignment_id = assignment["id"]

    for actor in ("member_one", "leader", "super_admin"):
        response = await context.client.get(
            f"/api/v1/task-assignments/{assignment_id}",
            headers=context.headers[actor],
        )
        assert response.status_code == 200

    hidden = await context.client.get(
        f"/api/v1/task-assignments/{assignment_id}",
        headers=context.headers["member_two"],
    )
    assert hidden.status_code == 404

    for actor in ("leader", "super_admin", "member_two"):
        forbidden = await context.client.patch(
            f"/api/v1/task-assignments/{assignment_id}/status",
            headers=context.headers[actor],
            json={"status": "in_progress"},
        )
        assert forbidden.status_code == 403

    started = await context.client.patch(
        f"/api/v1/task-assignments/{assignment_id}/status",
        headers=context.headers["member_one"],
        json={"status": "in_progress"},
    )
    assert started.status_code == 200, started.text
    assert started.json()["started_at"] is not None
    assert started.json()["completed_at"] is None

    done = await context.client.patch(
        f"/api/v1/task-assignments/{assignment_id}/status",
        headers=context.headers["member_one"],
        json={"status": "done"},
    )
    assert done.status_code == 200, done.text
    assert done.json()["completed_at"] is not None

    reopened = await context.client.patch(
        f"/api/v1/task-assignments/{assignment_id}/status",
        headers=context.headers["member_one"],
        json={"status": "in_progress"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["started_at"] == started.json()["started_at"]
    assert reopened.json()["completed_at"] is None


@pytest.mark.parametrize(
    ("actor", "expected_status"),
    [
        ("super_admin", 201),
        ("leader", 201),
        ("member_one", 201),
        ("unassigned", 404),
        ("team_admin", 404),
        ("project_owner", 404),
    ],
)
async def test_personal_task_file_upload_follows_assignment_visibility(
    personal_task_api_context: PersonalTaskApiContext,
    actor: str,
    expected_status: int,
) -> None:
    context = personal_task_api_context
    created = await _create_personal_task(context)
    task_id = created["task"]["id"]  # type: ignore[index]
    response = await context.client.post(
        f"/api/v1/tasks/{task_id}/files",
        headers=context.headers[actor],
        files={"file": ("shared.txt", b"shared", "text/plain")},
    )
    assert response.status_code == expected_status, response.text


async def test_personal_task_assignees_share_file_list_and_download(
    personal_task_api_context: PersonalTaskApiContext,
) -> None:
    context = personal_task_api_context
    created = await _create_personal_task(context)
    task_id = created["task"]["id"]  # type: ignore[index]
    uploaded = await _upload_personal_task_file(context, task_id, "member_one")

    for actor, can_control in (
        ("member_one", True),
        ("member_two", False),
        ("leader", True),
        ("super_admin", True),
    ):
        response = await context.client.get(
            f"/api/v1/tasks/{task_id}/files",
            headers=context.headers[actor],
        )
        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()] == [uploaded["id"]]
        assert response.json()[0]["permissions"] == {
            "can_modify": can_control,
            "can_delete": can_control,
        }
        download = await context.client.get(
            f"/api/v1/files/{uploaded['id']}/download",
            headers=context.headers[actor],
        )
        assert download.status_code == 200
        assert download.content == b"shared personal task file"

    for actor in ("unassigned", "team_admin", "project_owner"):
        hidden_list = await context.client.get(
            f"/api/v1/tasks/{task_id}/files",
            headers=context.headers[actor],
        )
        hidden_download = await context.client.get(
            f"/api/v1/files/{uploaded['id']}/download",
            headers=context.headers[actor],
        )
        assert hidden_list.status_code == 404
        assert hidden_download.status_code == 404


async def test_personal_task_file_control_permissions(
    personal_task_api_context: PersonalTaskApiContext,
) -> None:
    context = personal_task_api_context
    created = await _create_personal_task(context)
    task_id = created["task"]["id"]  # type: ignore[index]
    member_file = await _upload_personal_task_file(
        context, task_id, "member_one", filename="member.txt"
    )

    for actor in ("member_two", "project_owner", "team_admin"):
        response = await context.client.delete(
            f"/api/v1/files/{member_file['id']}",
            headers=context.headers[actor],
        )
        assert response.status_code == 403

    rename = await context.client.patch(
        f"/api/v1/files/{member_file['id']}",
        headers=context.headers["leader"],
        json={"original_name": "leader-renamed.txt"},
    )
    assert rename.status_code == 200
    assert rename.json()["original_name"] == "leader-renamed.txt"
    leader_delete = await context.client.delete(
        f"/api/v1/files/{member_file['id']}",
        headers=context.headers["leader"],
    )
    assert leader_delete.status_code == 204

    admin_file = await _upload_personal_task_file(
        context, task_id, "member_two", filename="admin.txt"
    )
    admin_rename = await context.client.patch(
        f"/api/v1/files/{admin_file['id']}",
        headers=context.headers["super_admin"],
        json={"original_name": "admin-renamed.txt"},
    )
    assert admin_rename.status_code == 200
    admin_delete = await context.client.delete(
        f"/api/v1/files/{admin_file['id']}",
        headers=context.headers["super_admin"],
    )
    assert admin_delete.status_code == 204

    own_file = await _upload_personal_task_file(context, task_id, "member_one", filename="own.txt")
    own_delete = await context.client.delete(
        f"/api/v1/files/{own_file['id']}",
        headers=context.headers["member_one"],
    )
    assert own_delete.status_code == 204


async def test_personal_task_files_do_not_leak_through_indexes(
    personal_task_api_context: PersonalTaskApiContext,
) -> None:
    context = personal_task_api_context
    created = await _create_personal_task(context)
    task_id = created["task"]["id"]  # type: ignore[index]
    uploaded = await _upload_personal_task_file(context, task_id, "member_one")

    for actor in ("leader", "super_admin", "member_one", "member_two"):
        response = await context.client.get(
            "/api/v1/files/index",
            headers=context.headers[actor],
        )
        assert response.status_code == 200
        assert uploaded["id"] in {item["id"] for item in response.json()}

    for actor in ("unassigned", "team_admin", "project_owner"):
        response = await context.client.get(
            "/api/v1/files/index",
            headers=context.headers[actor],
        )
        assert response.status_code == 200
        assert uploaded["id"] not in {item["id"] for item in response.json()}

    leader_project_index = await context.client.get(
        f"/api/v1/projects/{context.project_id}/file-index",
        headers=context.headers["leader"],
    )
    owner_project_index = await context.client.get(
        f"/api/v1/projects/{context.project_id}/file-index",
        headers=context.headers["project_owner"],
    )
    assert leader_project_index.status_code == 200
    assert uploaded["id"] in {
        item["id"] for group in leader_project_index.json()["tasks"] for item in group["files"]
    }
    assert owner_project_index.status_code == 200
    assert uploaded["id"] not in {
        item["id"] for group in owner_project_index.json()["tasks"] for item in group["files"]
    }


async def test_deleting_personal_task_cleans_database_and_physical_files(
    personal_task_api_context: PersonalTaskApiContext,
) -> None:
    context = personal_task_api_context
    created = await _create_personal_task(context)
    task_id = created["task"]["id"]  # type: ignore[index]
    uploaded = await _upload_personal_task_file(context, task_id, "member_one")
    file_id = UUID(str(uploaded["id"]))

    async with context.session_factory() as session:
        file = await session.get(File, file_id)
        assert file is not None
        stored_path = context.upload_root / file.storage_key
        assert stored_path.is_file()

    response = await context.client.delete(
        f"/api/v1/personal-tasks/{task_id}",
        headers=context.headers["leader"],
    )
    assert response.status_code == 204, response.text
    assert not stored_path.exists()
    async with context.session_factory() as session:
        assert await session.get(File, file_id) is None


@pytest.mark.parametrize("actor", ["leader", "super_admin"])
async def test_authorized_users_delete_personal_task_with_assignment_cascade(
    personal_task_api_context: PersonalTaskApiContext,
    actor: str,
) -> None:
    context = personal_task_api_context
    created = await _create_personal_task(context, title=f"Delete by {actor}")
    task_id = UUID(created["task"]["id"])  # type: ignore[index]

    response = await context.client.delete(
        f"/api/v1/personal-tasks/{task_id}", headers=context.headers[actor]
    )
    assert response.status_code == 204, response.text
    async with context.session_factory() as session:
        assert await session.get(Task, task_id) is None
        assert (
            await session.scalar(
                select(func.count())
                .select_from(TaskAssignment)
                .where(TaskAssignment.task_id == task_id)
            )
            == 0
        )


async def test_personal_task_delete_permission_and_collaborative_compatibility(
    personal_task_api_context: PersonalTaskApiContext,
) -> None:
    context = personal_task_api_context
    created = await _create_personal_task(context)
    personal_task_id = created["task"]["id"]  # type: ignore[index]

    forbidden = await context.client.delete(
        f"/api/v1/personal-tasks/{personal_task_id}",
        headers=context.headers["member_one"],
    )
    assert forbidden.status_code == 403

    collaborative = await context.client.post(
        f"/api/v1/projects/{context.project_id}/tasks",
        headers=context.headers["project_owner"],
        json={"title": "Collaborative API task"},
    )
    assert collaborative.status_code == 201, collaborative.text
    collaborative_id = UUID(collaborative.json()["id"])

    tasks = await context.client.get(
        f"/api/v1/projects/{context.project_id}/tasks",
        headers=context.headers["project_owner"],
    )
    assert tasks.status_code == 200
    assert [item["id"] for item in tasks.json()] == [str(collaborative_id)]

    status_response = await context.client.patch(
        f"/api/v1/tasks/{personal_task_id}/status",
        headers=context.headers["member_one"],
        json={"status": "in_progress"},
    )
    members_response = await context.client.get(
        f"/api/v1/tasks/{personal_task_id}/members",
        headers=context.headers["member_one"],
    )
    assert status_response.status_code == 403
    assert members_response.status_code == 403

    async with context.session_factory() as session:
        collaborative_task = await session.get(Task, collaborative_id)
        assert collaborative_task is not None
        assert collaborative_task.task_type is TaskType.COLLABORATIVE
        assert (
            await session.scalar(
                select(func.count())
                .select_from(TaskAssignment)
                .where(TaskAssignment.task_id == collaborative_id)
            )
            == 0
        )


async def test_project_personal_task_list_permissions_and_privacy(
    personal_task_api_context: PersonalTaskApiContext,
) -> None:
    context = personal_task_api_context
    created = await _create_personal_task(context, title="Managed history")
    endpoint = f"/api/v1/projects/{context.project_id}/personal-tasks"

    for actor in ("leader", "super_admin"):
        response = await context.client.get(endpoint, headers=context.headers[actor])
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["id"] == created["task"]["id"]  # type: ignore[index]
        assert payload["items"][0]["assignment_total"] == 2
        assert "assignments" not in payload["items"][0]
        assert "user" not in payload["items"][0]

    for actor in (
        "team_admin",
        "project_owner",
        "member_one",
        "unassigned",
    ):
        forbidden = await context.client.get(endpoint, headers=context.headers[actor])
        assert forbidden.status_code == 403


async def test_project_personal_task_list_aggregates_paginates_and_sorts(
    personal_task_api_context: PersonalTaskApiContext,
) -> None:
    context = personal_task_api_context
    now = datetime.now(UTC)
    early = await _create_personal_task(
        context, title="Open early", due_at=now + timedelta(hours=1)
    )
    late = await _create_personal_task(context, title="Open late", due_at=now + timedelta(hours=2))
    no_due = await _create_personal_task(context, title="Open no due")
    completed = await _create_personal_task(
        context, title="Completed but earliest", due_at=now + timedelta(minutes=10)
    )

    early_assignments = early["assignments"]  # type: ignore[index]
    for assignment, target in zip(
        early_assignments,
        ("in_progress", "in_review"),
        strict=True,
    ):
        actor = (
            "member_one"
            if assignment["user_id"] == str(context.user_ids["member_one"])
            else "member_two"
        )
        transitions = ("in_progress",) if target == "in_progress" else ("in_progress", "in_review")
        for transition in transitions:
            response = await context.client.patch(
                f"/api/v1/task-assignments/{assignment['id']}/status",
                headers=context.headers[actor],
                json={"status": transition},
            )
            assert response.status_code == 200, response.text

    for assignment in completed["assignments"]:  # type: ignore[union-attr]
        actor = (
            "member_one"
            if assignment["user_id"] == str(context.user_ids["member_one"])
            else "member_two"
        )
        for transition in ("in_progress", "done"):
            response = await context.client.patch(
                f"/api/v1/task-assignments/{assignment['id']}/status",
                headers=context.headers[actor],
                json={"status": transition},
            )
            assert response.status_code == 200, response.text

    endpoint = f"/api/v1/projects/{context.project_id}/personal-tasks"
    response = await context.client.get(endpoint, headers=context.headers["leader"])
    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["title"] for item in payload["items"]] == [
        "Open early",
        "Open late",
        "Open no due",
        "Completed but earliest",
    ]
    early_item = payload["items"][0]
    assert early_item["assignment_total"] == 2
    assert early_item["in_progress_count"] == 1
    assert early_item["in_review_count"] == 1
    assert early_item["todo_count"] == 0
    completed_item = payload["items"][-1]
    assert completed_item["done_count"] == 2

    page = await context.client.get(
        endpoint,
        headers=context.headers["leader"],
        params={"limit": 2, "offset": 1},
    )
    assert page.status_code == 200
    assert page.json()["total"] == 4
    assert page.json()["limit"] == 2
    assert page.json()["offset"] == 1
    assert [item["id"] for item in page.json()["items"]] == [
        late["task"]["id"],  # type: ignore[index]
        no_due["task"]["id"],  # type: ignore[index]
    ]


async def test_my_personal_task_count_is_status_accurate(
    personal_task_api_context: PersonalTaskApiContext,
) -> None:
    context = personal_task_api_context
    targets = (
        TaskStatus.TODO,
        TaskStatus.IN_PROGRESS,
        TaskStatus.IN_REVIEW,
        TaskStatus.DONE,
        TaskStatus.CANCELLED,
    )
    async with context.session_factory.begin() as session:
        records = [
            Task(
                project_id=context.project_id,
                title=f"Count {target.value}",
                created_by_id=context.user_ids["leader"],
                task_type=TaskType.PERSONAL,
            )
            for target in targets
        ]
        session.add_all(records)
        await session.flush()
        session.add_all(
            [
                TaskAssignment(
                    task_id=task.id,
                    user_id=context.user_ids["member_one"],
                    status=target,
                )
                for task, target in zip(records, targets, strict=True)
            ]
        )

    response = await context.client.get(
        "/api/v1/tasks/my/count",
        headers=context.headers["member_one"],
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "total": 5,
        "unfinished": 3,
        "todo": 1,
        "in_progress": 1,
        "in_review": 1,
        "done": 1,
        "cancelled": 1,
    }


async def test_my_personal_task_count_is_not_limited_by_list_page_size(
    personal_task_api_context: PersonalTaskApiContext,
) -> None:
    context = personal_task_api_context
    async with context.session_factory.begin() as session:
        records = [
            Task(
                project_id=context.project_id,
                title=f"Bulk personal task {index:03d}",
                created_by_id=context.user_ids["leader"],
                task_type=TaskType.PERSONAL,
            )
            for index in range(205)
        ]
        session.add_all(records)
        await session.flush()
        session.add_all(
            [
                TaskAssignment(
                    task_id=task.id,
                    user_id=context.user_ids["member_one"],
                )
                for task in records
            ]
        )

    page = await context.client.get(
        "/api/v1/tasks/my",
        headers=context.headers["member_one"],
        params={"limit": 200},
    )
    count = await context.client.get(
        "/api/v1/tasks/my/count",
        headers=context.headers["member_one"],
    )
    assert page.status_code == 200
    assert len(page.json()) == 200
    assert count.status_code == 200
    assert count.json()["total"] == 205
    assert count.json()["unfinished"] == 205


async def test_openapi_registers_static_and_personal_task_routes(
    personal_task_api_context: PersonalTaskApiContext,
) -> None:
    schema = (await personal_task_api_context.client.get("/openapi.json")).json()
    expected = {
        "/api/v1/projects/{project_id}/personal-tasks": "get",
        "/api/v1/tasks/my": "get",
        "/api/v1/tasks/my/count": "get",
        "/api/v1/personal-tasks/{task_id}": "get",
        "/api/v1/personal-tasks/{task_id}/assignments": "get",
        "/api/v1/task-assignments/{assignment_id}": "get",
        "/api/v1/task-assignments/{assignment_id}/status": "patch",
    }
    for path, method in expected.items():
        assert method in schema["paths"][path]
        assert schema["paths"][path][method]["security"] == [{"HTTPBearer": []}]
    assert "post" in schema["paths"]["/api/v1/projects/{project_id}/personal-tasks"]
    assert "delete" in schema["paths"]["/api/v1/personal-tasks/{task_id}"]
