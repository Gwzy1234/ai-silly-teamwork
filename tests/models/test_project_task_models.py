from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from silly_teamwork.db.base import Base
from silly_teamwork.models import (
    AttachmentMode,
    Project,
    ProjectMember,
    ProjectRole,
    ProjectStatus,
    Task,
    TaskAssignment,
    TaskMember,
    TaskPriority,
    TaskRole,
    TaskStatus,
    TaskType,
    Team,
    TeamMember,
    TeamRole,
    User,
)


@pytest_asyncio.fixture
async def session_factory(
    tmp_path: Path,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_path = tmp_path / "project-task-models.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory

    await engine.dispose()


async def _create_team_context(
    session: AsyncSession,
) -> tuple[User, User, User, Team]:
    creator = User(username="creator", password_hash="hash", display_name="Creator")
    second_owner = User(username="second-owner", password_hash="hash")
    reviewer = User(username="reviewer", password_hash="hash")
    session.add_all([creator, second_owner, reviewer])
    await session.flush()

    team = Team(name="Database Model Team", created_by_id=creator.id)
    session.add(team)
    await session.flush()
    session.add_all(
        [
            TeamMember(team_id=team.id, user_id=creator.id, role=TeamRole.OWNER),
            TeamMember(team_id=team.id, user_id=second_owner.id, role=TeamRole.MEMBER),
            TeamMember(team_id=team.id, user_id=reviewer.id, role=TeamRole.MEMBER),
        ]
    )
    await session.flush()
    return creator, second_owner, reviewer, team


@pytest.mark.asyncio
async def test_project_and_task_relationships_and_cascade(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        creator, _, reviewer, team = await _create_team_context(session)
        now = datetime.now(UTC)
        project = Project(
            team_id=team.id,
            name="Final Presentation",
            status=ProjectStatus.PLANNING,
            starts_at=now,
            due_at=now + timedelta(days=14),
            creator=creator,
        )
        owner = ProjectMember(project=project, user_id=creator.id, role=ProjectRole.OWNER)
        session.add_all([project, owner])
        await session.flush()

        task = Task(
            project=project,
            title="Create slides",
            status=TaskStatus.TODO,
            priority=TaskPriority.HIGH,
            starts_at=now,
            due_at=now + timedelta(days=7),
            creator=creator,
        )
        task_owner = TaskMember(task=task, user_id=creator.id, role=TaskRole.OWNER)
        task_reviewer = TaskMember(task=task, user_id=reviewer.id, role=TaskRole.REVIEWER)
        session.add_all([task, task_owner, task_reviewer])
        await session.flush()

        project_id = project.id
        task_id = task.id
        team_id = team.id
        assert project.team is team
        assert project.creator is creator
        assert owner in project.members
        assert task.project is project
        assert task.creator is creator
        assert task_owner in task.members
        assert task_reviewer.role is TaskRole.REVIEWER

    async with session_factory.begin() as session:
        team = await session.get(Team, team_id)
        assert team is not None
        await session.delete(team)

    async with session_factory() as session:
        assert await session.get(Project, project_id) is None
        assert await session.get(Task, task_id) is None
        assert await session.scalar(select(func.count()).select_from(ProjectMember)) == 0
        assert await session.scalar(select(func.count()).select_from(TaskMember)) == 0


@pytest.mark.asyncio
async def test_personal_task_assignments_keep_independent_statuses(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        creator, assignee, reviewer, team = await _create_team_context(session)
        project = Project(
            team_id=team.id,
            name="Personal Assignment Project",
            creator=creator,
        )
        task = Task(
            project=project,
            title="Complete the laboratory report",
            task_type=TaskType.PERSONAL,
            attachment_mode=AttachmentMode.SHARED,
            creator=creator,
        )
        first_assignment = TaskAssignment(
            task=task,
            user=assignee,
            status=TaskStatus.IN_PROGRESS,
        )
        second_assignment = TaskAssignment(
            task=task,
            user=reviewer,
            status=TaskStatus.DONE,
            started_at=datetime.now(UTC) - timedelta(hours=1),
            completed_at=datetime.now(UTC),
        )
        session.add_all([task, first_assignment, second_assignment])
        await session.flush()

        task_id = task.id
        assignee_id = assignee.id
        assert task.assignments == [first_assignment, second_assignment]
        assert first_assignment.task is task
        assert first_assignment.user is assignee
        assert first_assignment.status is TaskStatus.IN_PROGRESS
        assert second_assignment.status is TaskStatus.DONE
        assert task.status is TaskStatus.TODO

    async with session_factory() as session:
        loaded_assignee = await session.scalar(
            select(User)
            .where(User.id == assignee_id)
            .options(selectinload(User.task_assignments))
        )
        assert loaded_assignee is not None
        assert len(loaded_assignee.task_assignments) == 1
        assert loaded_assignee.task_assignments[0].task_id == task_id

    async with session_factory.begin() as session:
        task = await session.get(Task, task_id)
        assert task is not None
        await session.delete(task)

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(TaskAssignment)) == 0


@pytest.mark.asyncio
async def test_task_defaults_remain_collaborative_and_shared(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        creator, _, _, team = await _create_team_context(session)
        project = Project(team_id=team.id, name="Existing Task Project", creator=creator)
        task = Task(project=project, title="Existing workflow task", creator=creator)
        session.add(task)
        await session.flush()

        assert task.task_type is TaskType.COLLABORATIVE
        assert task.attachment_mode is AttachmentMode.SHARED


@pytest.mark.asyncio
async def test_task_assignment_rejects_duplicate_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        creator, assignee, _, team = await _create_team_context(session)
        project = Project(team_id=team.id, name="Unique Assignment Project", creator=creator)
        task = Task(
            project=project,
            title="Unique personal assignment",
            task_type=TaskType.PERSONAL,
            creator=creator,
        )
        session.add_all(
            [
                task,
                TaskAssignment(task=task, user=assignee),
            ]
        )
        await session.flush()
        task_id = task.id
        assignee_id = assignee.id

    async with session_factory() as session:
        session.add(TaskAssignment(task_id=task_id, user_id=assignee_id))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_project_allows_only_one_owner(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        creator, second_owner, _, team = await _create_team_context(session)
        project = Project(team_id=team.id, name="Unique Project Owner", created_by_id=creator.id)
        session.add_all(
            [
                project,
                ProjectMember(project=project, user_id=creator.id, role=ProjectRole.OWNER),
            ]
        )
        await session.flush()
        project_id = project.id
        second_owner_id = second_owner.id

    async with session_factory() as session:
        session.add(
            ProjectMember(
                project_id=project_id,
                user_id=second_owner_id,
                role=ProjectRole.OWNER,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_task_allows_only_one_owner(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        creator, second_owner, _, team = await _create_team_context(session)
        project = Project(team_id=team.id, name="Task Owner Project", created_by_id=creator.id)
        project.members.append(
            ProjectMember(user_id=creator.id, role=ProjectRole.OWNER)
        )
        task = Task(project=project, title="Unique Task Owner", created_by_id=creator.id)
        task.members.append(TaskMember(user_id=creator.id, role=TaskRole.OWNER))
        session.add(project)
        await session.flush()
        task_id = task.id
        second_owner_id = second_owner.id

    async with session_factory() as session:
        session.add(
            TaskMember(task_id=task_id, user_id=second_owner_id, role=TaskRole.OWNER)
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_project_and_task_deadline_constraints(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        creator, _, _, team = await _create_team_context(session)
        creator_id = creator.id
        team_id = team.id

    now = datetime.now(UTC)
    async with session_factory() as session:
        session.add(
            Project(
                team_id=team_id,
                name="Invalid Project Deadline",
                starts_at=now,
                due_at=now - timedelta(seconds=1),
                created_by_id=creator_id,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

    async with session_factory.begin() as session:
        project = Project(team_id=team_id, name="Valid Project", created_by_id=creator_id)
        session.add(project)
        await session.flush()
        project_id = project.id

    async with session_factory() as session:
        session.add(
            Task(
                project_id=project_id,
                title="Invalid Task Deadline",
                starts_at=now,
                due_at=now - timedelta(seconds=1),
                created_by_id=creator_id,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
