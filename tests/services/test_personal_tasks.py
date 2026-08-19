from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from silly_teamwork.db.base import Base
from silly_teamwork.models import (
    AttachmentMode,
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
from silly_teamwork.repositories import task_assignments
from silly_teamwork.schemas.personal_task import PersonalTaskCreate
from silly_teamwork.schemas.task import TaskCreate
from silly_teamwork.services.exceptions import (
    PersonalTaskValidationError,
    ProjectAccessDeniedError,
    TaskAccessDeniedError,
    TaskAssignmentAccessDeniedError,
    TaskNotFoundError,
)
from silly_teamwork.services.personal_tasks import PersonalTaskService
from silly_teamwork.services.task_assignments import TaskAssignmentService
from silly_teamwork.services.tasks import TaskService


@dataclass(frozen=True, slots=True)
class PersonalTaskContext:
    session_factory: async_sessionmaker[AsyncSession]
    leader_id: UUID
    team_admin_id: UUID
    project_owner_id: UUID
    first_member_id: UUID
    second_member_id: UUID
    outsider_id: UUID
    super_admin_id: UUID
    team_id: UUID
    project_id: UUID


@pytest_asyncio.fixture
async def personal_task_context(tmp_path: Path) -> AsyncIterator[PersonalTaskContext]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'personal-tasks.db'}")

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
            name: User(username=name, password_hash="hash")
            for name in (
                "personal-leader",
                "personal-team-admin",
                "personal-project-owner",
                "personal-first-member",
                "personal-second-member",
                "personal-outsider",
                "personal-super-admin",
            )
        }
        session.add_all(users.values())
        await session.flush()
        team = Team(
            name="Personal Task Team",
            created_by_id=users["personal-leader"].id,
        )
        session.add(team)
        await session.flush()
        session.add_all(
            [
                TeamMember(
                    team_id=team.id,
                    user_id=users["personal-leader"].id,
                    role=TeamRole.OWNER,
                ),
                TeamMember(
                    team_id=team.id,
                    user_id=users["personal-team-admin"].id,
                    role=TeamRole.ADMIN,
                ),
                TeamMember(
                    team_id=team.id,
                    user_id=users["personal-project-owner"].id,
                    role=TeamRole.MEMBER,
                ),
                TeamMember(
                    team_id=team.id,
                    user_id=users["personal-first-member"].id,
                    role=TeamRole.MEMBER,
                ),
                TeamMember(
                    team_id=team.id,
                    user_id=users["personal-second-member"].id,
                    role=TeamRole.MEMBER,
                ),
            ]
        )
        session.add(
            SystemAdmin(
                user_id=users["personal-super-admin"].id,
                role=SystemAdminRole.SUPER_ADMIN,
            )
        )
        project = Project(
            team_id=team.id,
            name="Personal Task Subject",
            created_by_id=users["personal-leader"].id,
        )
        session.add(project)
        await session.flush()
        session.add(
            ProjectMember(
                project_id=project.id,
                user_id=users["personal-project-owner"].id,
                role=ProjectRole.OWNER,
            )
        )

        context = PersonalTaskContext(
            session_factory=factory,
            leader_id=users["personal-leader"].id,
            team_admin_id=users["personal-team-admin"].id,
            project_owner_id=users["personal-project-owner"].id,
            first_member_id=users["personal-first-member"].id,
            second_member_id=users["personal-second-member"].id,
            outsider_id=users["personal-outsider"].id,
            super_admin_id=users["personal-super-admin"].id,
            team_id=team.id,
            project_id=project.id,
        )

    yield context
    await engine.dispose()


async def _user(session: AsyncSession, user_id: UUID) -> User:
    user = await session.get(User, user_id)
    assert user is not None
    return user


def _payload(
    context: PersonalTaskContext,
    *,
    title: str = "Complete laboratory report",
    assignee_user_ids: list[UUID] | None = None,
    attachment_mode: AttachmentMode = AttachmentMode.SHARED,
    due_at: datetime | None = None,
) -> PersonalTaskCreate:
    return PersonalTaskCreate(
        title=title,
        description="Submit an individual report",
        assignee_user_ids=assignee_user_ids
        if assignee_user_ids is not None
        else [context.first_member_id, context.second_member_id],
        attachment_mode=attachment_mode,
        due_at=due_at,
    )


async def _create_personal_task(
    context: PersonalTaskContext,
    *,
    creator_id: UUID | None = None,
    title: str = "Complete laboratory report",
) -> UUID:
    service = PersonalTaskService()
    async with context.session_factory() as session:
        creator = await _user(session, creator_id or context.leader_id)
        task = await service.create_personal_task(
            session,
            creator,
            context.project_id,
            _payload(context, title=title),
        )
        return task.id


@pytest.mark.asyncio
@pytest.mark.parametrize("actor_id_name", ["leader_id", "super_admin_id"])
async def test_leader_and_super_admin_can_create_personal_tasks(
    personal_task_context: PersonalTaskContext,
    actor_id_name: str,
) -> None:
    context = personal_task_context
    service = PersonalTaskService()
    async with context.session_factory() as session:
        actor = await _user(session, getattr(context, actor_id_name))
        task = await service.create_personal_task(
            session, actor, context.project_id, _payload(context)
        )
        task_id = task.id
        assert task.task_type is TaskType.PERSONAL
        assert task.attachment_mode is AttachmentMode.SHARED
        assert task.status is TaskStatus.TODO

    async with context.session_factory() as session:
        assignments = await task_assignments.list_for_task(session, task_id)
        assert {item.user_id for item in assignments} == {
            context.first_member_id,
            context.second_member_id,
        }
        assert {item.status for item in assignments} == {TaskStatus.TODO}
        assert await session.scalar(
            select(func.count())
            .select_from(TaskMember)
            .where(TaskMember.task_id == task_id)
        ) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "actor_id_name",
    ["team_admin_id", "project_owner_id", "first_member_id"],
)
async def test_disallowed_roles_cannot_create_personal_tasks(
    personal_task_context: PersonalTaskContext,
    actor_id_name: str,
) -> None:
    context = personal_task_context
    service = PersonalTaskService()
    async with context.session_factory() as session:
        actor = await _user(session, getattr(context, actor_id_name))
        with pytest.raises(ProjectAccessDeniedError):
            await service.create_personal_task(
                session, actor, context.project_id, _payload(context)
            )


@pytest.mark.asyncio
async def test_personal_task_creation_validates_assignees_and_attachment_mode(
    personal_task_context: PersonalTaskContext,
) -> None:
    context = personal_task_context
    service = PersonalTaskService()
    async with context.session_factory() as session:
        leader = await _user(session, context.leader_id)
        invalid_payloads = [
            _payload(context, assignee_user_ids=[]),
            _payload(context, assignee_user_ids=[context.outsider_id]),
            _payload(
                context,
                assignee_user_ids=[
                    context.first_member_id,
                    context.first_member_id,
                ],
            ),
            _payload(context, attachment_mode=AttachmentMode.INDIVIDUAL),
        ]
        for payload in invalid_payloads:
            with pytest.raises(PersonalTaskValidationError):
                await service.create_personal_task(
                    session, leader, context.project_id, payload
                )

        assert await session.scalar(
            select(func.count()).select_from(Task).where(Task.task_type == TaskType.PERSONAL)
        ) == 0


@pytest.mark.asyncio
async def test_personal_task_creation_rolls_back_when_assignment_creation_fails(
    personal_task_context: PersonalTaskContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = personal_task_context
    service = PersonalTaskService()

    def fail_assignment_creation(
        session: AsyncSession, assignments: list[TaskAssignment]
    ) -> None:
        session.add(assignments[0])
        raise RuntimeError("simulated assignment persistence failure")

    monkeypatch.setattr(task_assignments, "add_all", fail_assignment_creation)
    async with context.session_factory() as session:
        leader = await _user(session, context.leader_id)
        with pytest.raises(RuntimeError, match="simulated assignment"):
            await service.create_personal_task(
                session, leader, context.project_id, _payload(context)
            )

    async with context.session_factory() as session:
        assert await session.scalar(
            select(func.count()).select_from(Task).where(Task.task_type == TaskType.PERSONAL)
        ) == 0
        assert await session.scalar(
            select(func.count()).select_from(TaskAssignment)
        ) == 0


@pytest.mark.asyncio
async def test_personal_task_visibility_and_progress_permissions(
    personal_task_context: PersonalTaskContext,
) -> None:
    context = personal_task_context
    task_id = await _create_personal_task(context)
    service = PersonalTaskService()

    async with context.session_factory() as session:
        leader = await _user(session, context.leader_id)
        super_admin = await _user(session, context.super_admin_id)
        assignee = await _user(session, context.first_member_id)
        unassigned = await _user(session, context.project_owner_id)
        team_admin = await _user(session, context.team_admin_id)

        assert (await service.get_personal_task(session, leader, task_id)).id == task_id
        assert (await service.get_personal_task(session, super_admin, task_id)).id == task_id
        assert (await service.get_personal_task(session, assignee, task_id)).id == task_id
        assert len(await service.list_assignments(session, leader, task_id)) == 2
        assert len(await service.list_assignments(session, super_admin, task_id)) == 2
        with pytest.raises(TaskNotFoundError):
            await service.get_personal_task(session, unassigned, task_id)
        with pytest.raises(TaskNotFoundError):
            await service.get_personal_task(session, team_admin, task_id)
        with pytest.raises(TaskAccessDeniedError):
            await service.list_assignments(session, assignee, task_id)


@pytest.mark.asyncio
async def test_assignment_statuses_are_independent_and_track_timestamps(
    personal_task_context: PersonalTaskContext,
) -> None:
    context = personal_task_context
    task_id = await _create_personal_task(context)
    service = TaskAssignmentService()

    async with context.session_factory() as session:
        assignments = await task_assignments.list_for_task(session, task_id)
        by_user = {item.user_id: item for item in assignments}
        first = by_user[context.first_member_id]
        second = by_user[context.second_member_id]
        first_member = await _user(session, context.first_member_id)

        in_progress = await service.change_status(
            session, first_member, first.id, TaskStatus.IN_PROGRESS
        )
        started_at = in_progress.started_at
        assert started_at is not None
        assert in_progress.completed_at is None

        in_review = await service.change_status(
            session, first_member, first.id, TaskStatus.IN_REVIEW
        )
        assert in_review.started_at == started_at

        done = await service.change_status(
            session, first_member, first.id, TaskStatus.DONE
        )
        assert done.completed_at is not None

        reopened = await service.change_status(
            session, first_member, first.id, TaskStatus.IN_PROGRESS
        )
        assert reopened.started_at == started_at
        assert reopened.completed_at is None

        unchanged_second = await task_assignments.get_by_id(session, second.id)
        assert unchanged_second is not None
        assert unchanged_second.status is TaskStatus.TODO
        task = await session.get(Task, task_id)
        assert task is not None and task.status is TaskStatus.TODO


@pytest.mark.asyncio
async def test_only_assignee_can_change_assignment_status(
    personal_task_context: PersonalTaskContext,
) -> None:
    context = personal_task_context
    task_id = await _create_personal_task(context)
    service = TaskAssignmentService()
    async with context.session_factory() as session:
        assignment = await task_assignments.get_by_task_and_user(
            session, task_id, context.first_member_id
        )
        assert assignment is not None
        for actor_id in (
            context.second_member_id,
            context.leader_id,
            context.super_admin_id,
        ):
            actor = await _user(session, actor_id)
            with pytest.raises(TaskAssignmentAccessDeniedError):
                await service.change_status(
                    session, actor, assignment.id, TaskStatus.IN_PROGRESS
                )


@pytest.mark.asyncio
async def test_my_assignments_support_filters_and_eager_context(
    personal_task_context: PersonalTaskContext,
) -> None:
    context = personal_task_context
    due_at = datetime.now(UTC) + timedelta(days=1)
    service = PersonalTaskService()
    assignment_service = TaskAssignmentService()
    async with context.session_factory() as session:
        leader = await _user(session, context.leader_id)
        task = await service.create_personal_task(
            session,
            leader,
            context.project_id,
            _payload(context, due_at=due_at),
        )
        task_id = task.id

    async with context.session_factory() as session:
        member = await _user(session, context.first_member_id)
        items = await assignment_service.list_my_assignments(
            session,
            member,
            status=TaskStatus.TODO,
            team_id=context.team_id,
            project_id=context.project_id,
            due_before=due_at + timedelta(minutes=1),
            due_after=due_at - timedelta(minutes=1),
        )
        assert len(items) == 1
        assert items[0].task_id == task_id
        assert items[0].user.id == context.first_member_id
        assert items[0].task.project.id == context.project_id
        assert items[0].task.project.team.id == context.team_id


@pytest.mark.asyncio
@pytest.mark.parametrize("actor_id_name", ["leader_id", "super_admin_id"])
async def test_leader_and_super_admin_can_delete_personal_task_with_cascade(
    personal_task_context: PersonalTaskContext,
    actor_id_name: str,
) -> None:
    context = personal_task_context
    task_id = await _create_personal_task(
        context, title=f"Delete by {actor_id_name}"
    )
    service = PersonalTaskService()
    async with context.session_factory() as session:
        actor = await _user(session, getattr(context, actor_id_name))
        await service.delete_personal_task(session, actor, task_id)

    async with context.session_factory() as session:
        assert await session.get(Task, task_id) is None
        assert await session.scalar(
            select(func.count())
            .select_from(TaskAssignment)
            .where(TaskAssignment.task_id == task_id)
        ) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "actor_id_name",
    ["team_admin_id", "project_owner_id", "first_member_id"],
)
async def test_disallowed_roles_cannot_delete_personal_task(
    personal_task_context: PersonalTaskContext,
    actor_id_name: str,
) -> None:
    context = personal_task_context
    task_id = await _create_personal_task(context)
    service = PersonalTaskService()
    async with context.session_factory() as session:
        member = await _user(session, getattr(context, actor_id_name))
        with pytest.raises(TaskAccessDeniedError):
            await service.delete_personal_task(session, member, task_id)
        assert await session.get(Task, task_id) is not None


@pytest.mark.asyncio
async def test_collaborative_task_service_behavior_is_unchanged(
    personal_task_context: PersonalTaskContext,
) -> None:
    context = personal_task_context
    service = TaskService()
    personal_task_id = await _create_personal_task(context)
    async with context.session_factory() as session:
        project_owner = await _user(session, context.project_owner_id)
        collaborative = await service.create_task(
            session,
            project_owner,
            context.project_id,
            TaskCreate(
                title="Collaborative regression task",
                owner_user_id=context.project_owner_id,
            ),
        )
        tasks = await service.list_tasks(session, project_owner, context.project_id)
        assert collaborative.task_type is TaskType.COLLABORATIVE
        assert collaborative.attachment_mode is AttachmentMode.SHARED
        assert {task.id for task in tasks} == {collaborative.id}
        assert personal_task_id not in {task.id for task in tasks}
        assert await session.scalar(
            select(func.count())
            .select_from(TaskMember)
            .where(TaskMember.task_id == collaborative.id)
        ) == 1
