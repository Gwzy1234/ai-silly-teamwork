from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from silly_teamwork.core.file_storage import LocalFileStorage
from silly_teamwork.db.base import Base
from silly_teamwork.models import (
    File,
    Notification,
    NotificationType,
    Project,
    ProjectMember,
    ProjectRole,
    SystemAdmin,
    SystemAdminRole,
    Task,
    TaskMember,
    TaskRole,
    TaskStatus,
    Team,
    TeamMember,
    TeamRole,
    User,
)
from silly_teamwork.repositories import project_members, task_members
from silly_teamwork.schemas.project import ProjectCreate, ProjectMemberAdd, ProjectUpdate
from silly_teamwork.schemas.task import TaskCreate, TaskMemberAdd, TaskUpdate
from silly_teamwork.services.collaboration_access import CollaborationAccessService
from silly_teamwork.services.exceptions import (
    ProjectAccessDeniedError,
    ProjectNotFoundError,
    TaskAccessDeniedError,
)
from silly_teamwork.services.file_cleanup import FileCleanupService
from silly_teamwork.services.projects import ProjectService
from silly_teamwork.services.tasks import TaskService
from silly_teamwork.services.teams import TeamService


@dataclass(frozen=True, slots=True)
class CollaborationContext:
    session_factory: async_sessionmaker[AsyncSession]
    leader_id: UUID
    project_owner_id: UUID
    member_id: UUID
    collaborator_id: UUID
    reviewer_id: UUID
    outsider_id: UUID
    admin_id: UUID
    team_id: UUID
    project_id: UUID
    task_id: UUID
    project_file_id: UUID
    task_file_id: UUID


@pytest_asyncio.fixture
async def collaboration_context(tmp_path: Path) -> AsyncIterator[CollaborationContext]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'collaboration.db'}")

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
                "leader",
                "project-owner",
                "member",
                "collaborator",
                "reviewer",
                "outsider",
                "system-admin",
            )
        }
        session.add_all(users.values())
        await session.flush()
        team = Team(name="Collaboration Team", created_by_id=users["leader"].id)
        session.add(team)
        await session.flush()
        session.add_all(
            TeamMember(team_id=team.id, user_id=user.id, role=role)
            for user, role in (
                (users["leader"], TeamRole.OWNER),
                (users["project-owner"], TeamRole.MEMBER),
                (users["member"], TeamRole.MEMBER),
                (users["collaborator"], TeamRole.MEMBER),
                (users["reviewer"], TeamRole.MEMBER),
            )
        )
        session.add(
            SystemAdmin(user_id=users["system-admin"].id, role=SystemAdminRole.SUPER_ADMIN)
        )
        project = Project(
            team_id=team.id,
            name="Final Project",
            created_by_id=users["leader"].id,
        )
        session.add(project)
        await session.flush()
        session.add_all(
            [
                ProjectMember(
                    project_id=project.id,
                    user_id=users["project-owner"].id,
                    role=ProjectRole.OWNER,
                ),
                ProjectMember(
                    project_id=project.id,
                    user_id=users["member"].id,
                    role=ProjectRole.MEMBER,
                ),
                ProjectMember(
                    project_id=project.id,
                    user_id=users["collaborator"].id,
                    role=ProjectRole.MEMBER,
                ),
                ProjectMember(
                    project_id=project.id,
                    user_id=users["reviewer"].id,
                    role=ProjectRole.MEMBER,
                ),
            ]
        )
        task = Task(
            project_id=project.id,
            title="Prepare slides",
            created_by_id=users["project-owner"].id,
        )
        session.add(task)
        await session.flush()
        session.add_all(
            [
                TaskMember(
                    task_id=task.id,
                    user_id=users["member"].id,
                    role=TaskRole.OWNER,
                ),
                TaskMember(
                    task_id=task.id,
                    user_id=users["collaborator"].id,
                    role=TaskRole.COLLABORATOR,
                ),
                TaskMember(
                    task_id=task.id,
                    user_id=users["reviewer"].id,
                    role=TaskRole.REVIEWER,
                ),
            ]
        )
        project_file = File(
            project_id=project.id,
            uploaded_by_id=users["member"].id,
            original_name="notes.txt",
            storage_key="tests/project-notes.txt",
            content_type="text/plain",
            size_bytes=10,
        )
        task_file = File(
            task_id=task.id,
            uploaded_by_id=users["collaborator"].id,
            original_name="slides.pptx",
            storage_key="tests/slides.pptx",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            size_bytes=20,
        )
        session.add_all([project_file, task_file])
        await session.flush()

        context = CollaborationContext(
            session_factory=factory,
            leader_id=users["leader"].id,
            project_owner_id=users["project-owner"].id,
            member_id=users["member"].id,
            collaborator_id=users["collaborator"].id,
            reviewer_id=users["reviewer"].id,
            outsider_id=users["outsider"].id,
            admin_id=users["system-admin"].id,
            team_id=team.id,
            project_id=project.id,
            task_id=task.id,
            project_file_id=project_file.id,
            task_file_id=task_file.id,
        )

    yield context
    await engine.dispose()


async def _user(session: AsyncSession, user_id: UUID) -> User:
    user = await session.get(User, user_id)
    assert user is not None
    return user


async def _notifications_for_task(
    session: AsyncSession, task_id: UUID, *, user_id: UUID | None = None
) -> list[Notification]:
    statement = select(Notification).where(Notification.related_task_id == task_id)
    if user_id is not None:
        statement = statement.where(Notification.user_id == user_id)
    result = await session.execute(statement.order_by(Notification.created_at, Notification.id))
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_access_matrix(collaboration_context: CollaborationContext) -> None:
    ctx = collaboration_context
    access = CollaborationAccessService()
    async with ctx.session_factory() as session:
        leader = await _user(session, ctx.leader_id)
        owner = await _user(session, ctx.project_owner_id)
        member = await _user(session, ctx.member_id)
        collaborator = await _user(session, ctx.collaborator_id)
        reviewer = await _user(session, ctx.reviewer_id)
        outsider = await _user(session, ctx.outsider_id)
        admin = await _user(session, ctx.admin_id)

        assert await access.can_access_project(session, leader, ctx.project_id)
        assert await access.can_access_project(session, owner, ctx.project_id)
        assert await access.can_access_project(session, member, ctx.project_id)
        assert not await access.can_access_project(session, outsider, ctx.project_id)
        assert not await access.can_access_project(session, admin, ctx.project_id)

        assert await access.can_manage_project(session, leader, ctx.project_id)
        assert await access.can_manage_project(session, owner, ctx.project_id)
        assert not await access.can_manage_project(session, member, ctx.project_id)
        assert not await access.can_manage_project(session, admin, ctx.project_id)

        assert await access.can_manage_task(session, leader, ctx.task_id)
        assert await access.can_manage_task(session, owner, ctx.task_id)
        assert await access.can_manage_task(session, member, ctx.task_id)
        assert not await access.can_manage_task(session, outsider, ctx.task_id)
        assert not await access.can_manage_task(session, admin, ctx.task_id)

        assert await access.can_upload_project_file(session, member, ctx.project_id)
        assert await access.can_upload_task_file(session, member, ctx.task_id)
        assert await access.can_upload_task_file(session, collaborator, ctx.task_id)
        assert await access.can_upload_task_file(session, reviewer, ctx.task_id)
        assert not await access.can_upload_task_file(session, outsider, ctx.task_id)
        admin_file_scope = await access.get_file_access_scope(session, admin)
        assert admin_file_scope.can_access_all_files
        assert (
            await access.require_project_file_access(session, admin, ctx.project_id)
        ).id == ctx.project_id
        with pytest.raises(ProjectNotFoundError):
            await access.require_project_access(session, outsider, ctx.project_id)


@pytest.mark.asyncio
async def test_file_control_matrix(collaboration_context: CollaborationContext) -> None:
    ctx = collaboration_context
    access = CollaborationAccessService()
    async with ctx.session_factory() as session:
        leader = await _user(session, ctx.leader_id)
        owner = await _user(session, ctx.project_owner_id)
        uploader = await _user(session, ctx.member_id)
        reviewer = await _user(session, ctx.reviewer_id)
        admin = await _user(session, ctx.admin_id)

        for actor in (leader, owner, uploader, admin):
            assert await access.can_modify_file(session, actor, ctx.project_file_id)
            assert await access.can_delete_file(session, actor, ctx.project_file_id)
        assert not await access.can_modify_file(session, reviewer, ctx.project_file_id)
        assert await access.can_delete_file(session, admin, ctx.task_file_id)

        assert await access.can_delete_task(session, leader, ctx.task_id)
        assert await access.can_delete_task(session, owner, ctx.task_id)
        assert await access.can_delete_task(session, admin, ctx.task_id)
        assert not await access.can_delete_task(session, uploader, ctx.task_id)
        assert not await access.can_delete_task(session, reviewer, ctx.task_id)

        assert await access.can_delete_project(session, leader, ctx.project_id)
        assert await access.can_delete_project(session, admin, ctx.project_id)
        assert not await access.can_delete_project(session, owner, ctx.project_id)
        assert not await access.can_delete_project(session, uploader, ctx.project_id)

        assert await access.can_delete_team(session, leader, ctx.team_id)
        assert await access.can_delete_team(session, admin, ctx.team_id)
        assert not await access.can_delete_team(session, owner, ctx.team_id)
        assert not await access.can_delete_team(session, uploader, ctx.team_id)


@pytest.mark.asyncio
async def test_task_delete_restores_physical_files_when_commit_fails(
    collaboration_context: CollaborationContext,
    tmp_path: Path,
) -> None:
    ctx = collaboration_context
    storage = LocalFileStorage(tmp_path / "uploads")
    stored_path = storage.resolve("tests/slides.pptx")
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    stored_path.write_bytes(b"slides")
    service = TaskService(cleanup_service=FileCleanupService(storage))

    async with ctx.session_factory() as session:
        project_owner = await _user(session, ctx.project_owner_id)

        def fail_commit(_: object) -> None:
            raise RuntimeError("simulated commit failure")

        event.listen(session.sync_session, "before_commit", fail_commit)
        try:
            with pytest.raises(RuntimeError, match="simulated commit failure"):
                await service.delete_task(session, project_owner, ctx.task_id)
        finally:
            event.remove(session.sync_session, "before_commit", fail_commit)

    assert stored_path.read_bytes() == b"slides"
    assert not list(stored_path.parent.glob(".*.deleting-*"))
    async with ctx.session_factory() as session:
        assert await session.get(Task, ctx.task_id) is not None
        assert await session.get(File, ctx.task_file_id) is not None


@pytest.mark.asyncio
async def test_project_delete_restores_all_physical_files_when_commit_fails(
    collaboration_context: CollaborationContext,
    tmp_path: Path,
) -> None:
    ctx = collaboration_context
    storage = LocalFileStorage(tmp_path / "uploads")
    project_path = storage.resolve("tests/project-notes.txt")
    task_path = storage.resolve("tests/slides.pptx")
    project_path.parent.mkdir(parents=True, exist_ok=True)
    project_path.write_bytes(b"notes")
    task_path.write_bytes(b"slides")
    service = ProjectService(cleanup_service=FileCleanupService(storage))

    async with ctx.session_factory() as session:
        leader = await _user(session, ctx.leader_id)

        def fail_commit(_: object) -> None:
            raise RuntimeError("simulated project commit failure")

        event.listen(session.sync_session, "before_commit", fail_commit)
        try:
            with pytest.raises(RuntimeError, match="simulated project commit failure"):
                await service.delete_project(session, leader, ctx.project_id)
        finally:
            event.remove(session.sync_session, "before_commit", fail_commit)

    assert project_path.read_bytes() == b"notes"
    assert task_path.read_bytes() == b"slides"
    assert not list(project_path.parent.glob(".*.deleting-*"))
    async with ctx.session_factory() as session:
        assert await session.get(Project, ctx.project_id) is not None
        assert await session.get(Task, ctx.task_id) is not None
        assert await session.get(File, ctx.project_file_id) is not None
        assert await session.get(File, ctx.task_file_id) is not None


@pytest.mark.asyncio
async def test_team_delete_restores_entire_tree_and_files_when_commit_fails(
    collaboration_context: CollaborationContext,
    tmp_path: Path,
) -> None:
    ctx = collaboration_context
    storage = LocalFileStorage(tmp_path / "uploads")
    project_path = storage.resolve("tests/project-notes.txt")
    task_path = storage.resolve("tests/slides.pptx")
    project_path.parent.mkdir(parents=True, exist_ok=True)
    project_path.write_bytes(b"notes")
    task_path.write_bytes(b"slides")
    service = TeamService(cleanup_service=FileCleanupService(storage))

    async with ctx.session_factory() as session:
        leader = await _user(session, ctx.leader_id)

        def fail_commit(_: object) -> None:
            raise RuntimeError("simulated team commit failure")

        event.listen(session.sync_session, "before_commit", fail_commit)
        try:
            with pytest.raises(RuntimeError, match="simulated team commit failure"):
                await service.delete_team(session, leader, ctx.team_id)
        finally:
            event.remove(session.sync_session, "before_commit", fail_commit)

    assert project_path.read_bytes() == b"notes"
    assert task_path.read_bytes() == b"slides"
    assert not list(project_path.parent.glob(".*.deleting-*"))
    async with ctx.session_factory() as session:
        assert await session.get(Team, ctx.team_id) is not None
        assert await session.get(Project, ctx.project_id) is not None
        assert await session.get(Task, ctx.task_id) is not None
        assert await session.get(File, ctx.project_file_id) is not None
        assert await session.get(File, ctx.task_file_id) is not None


@pytest.mark.asyncio
async def test_project_service_lifecycle_and_permissions(
    collaboration_context: CollaborationContext,
) -> None:
    ctx = collaboration_context
    service = ProjectService()
    async with ctx.session_factory() as session:
        leader = await _user(session, ctx.leader_id)
        created = await service.create_project(
            session,
            leader,
            ctx.team_id,
            ProjectCreate(name="New Project", owner_user_id=ctx.member_id),
        )
        created_id = created.id
    async with ctx.session_factory() as session:
        owner = await project_members.get_owner(session, created_id)
        assert owner is not None and owner.user_id == ctx.member_id
        member = await _user(session, ctx.member_id)
        visible_projects = await service.list_projects(session, member, ctx.team_id)
        assert created_id in {project.id for project in visible_projects}
        assert (await service.get_project(session, member, created_id)).id == created_id
        updated = await service.update_project(
            session, member, created_id, ProjectUpdate(description="Updated")
        )
        assert updated.description == "Updated"
        outsider = await _user(session, ctx.outsider_id)
        with pytest.raises(ProjectNotFoundError):
            await service.get_project(session, outsider, created_id)

    async with ctx.session_factory() as session:
        leader = await _user(session, ctx.leader_id)
        await service.add_member(
            session, leader, created_id, ProjectMemberAdd(user_id=ctx.reviewer_id)
        )
        transferred = await service.transfer_owner(
            session, leader, created_id, ctx.reviewer_id
        )
        assert transferred.user_id == ctx.reviewer_id
        old_owner = await project_members.get_by_project_and_user(
            session, created_id, ctx.member_id
        )
        assert old_owner is not None and old_owner.role is ProjectRole.MEMBER
        await service.remove_member(session, leader, created_id, ctx.member_id)

    async with ctx.session_factory() as session:
        admin = await _user(session, ctx.admin_id)
        with pytest.raises(ProjectAccessDeniedError):
            await service.update_project(
                session, admin, created_id, ProjectUpdate(name="Admin cannot edit")
            )


@pytest.mark.asyncio
async def test_task_service_lifecycle_status_and_permissions(
    collaboration_context: CollaborationContext,
) -> None:
    ctx = collaboration_context
    service = TaskService()
    async with ctx.session_factory() as session:
        project_owner = await _user(session, ctx.project_owner_id)
        created = await service.create_task(
            session,
            project_owner,
            ctx.project_id,
            TaskCreate(title="Write report", owner_user_id=ctx.member_id),
        )
        created_id = created.id

    async with ctx.session_factory() as session:
        task_owner = await _user(session, ctx.member_id)
        updated = await service.update_task(
            session, task_owner, created_id, TaskUpdate(description="Owner update")
        )
        assert updated.description == "Owner update"
        changed = await service.change_status(
            session, task_owner, created_id, TaskStatus.IN_PROGRESS
        )
        assert changed.status is TaskStatus.IN_PROGRESS

    async with ctx.session_factory() as session:
        project_owner = await _user(session, ctx.project_owner_id)
        await service.add_member(
            session,
            project_owner,
            created_id,
            TaskMemberAdd(user_id=ctx.collaborator_id, role=TaskRole.COLLABORATOR),
        )
        collaborator = await _user(session, ctx.collaborator_id)
        changed = await service.change_status(
            session, collaborator, created_id, TaskStatus.IN_REVIEW
        )
        assert changed.status is TaskStatus.IN_REVIEW

    async with ctx.session_factory() as session:
        project_owner = await _user(session, ctx.project_owner_id)
        await service.add_member(
            session,
            project_owner,
            created_id,
            TaskMemberAdd(user_id=ctx.reviewer_id, role=TaskRole.REVIEWER),
        )
        reviewer = await _user(session, ctx.reviewer_id)
        done = await service.change_status(session, reviewer, created_id, TaskStatus.DONE)
        assert done.completed_at is not None
        transferred = await service.transfer_owner(
            session, project_owner, created_id, ctx.collaborator_id
        )
        assert transferred.role is TaskRole.OWNER
        old_owner = await task_members.get_by_task_and_user(session, created_id, ctx.member_id)
        assert old_owner is not None and old_owner.role is TaskRole.COLLABORATOR
        assert (await service.get_task(session, project_owner, created_id)).id == created_id
        assert created_id in {
            task.id for task in await service.list_tasks(session, project_owner, ctx.project_id)
        }
        await service.remove_member(session, project_owner, created_id, ctx.reviewer_id)
        assert await task_members.get_by_task_and_user(
            session, created_id, ctx.reviewer_id
        ) is None

    async with ctx.session_factory() as session:
        outsider = await _user(session, ctx.outsider_id)
        with pytest.raises(TaskAccessDeniedError):
            await service.update_task(
                session, outsider, created_id, TaskUpdate(title="Forbidden")
            )
        admin = await _user(session, ctx.admin_id)
        with pytest.raises(TaskAccessDeniedError):
            await service.update_task(session, admin, created_id, TaskUpdate(title="Admin"))


@pytest.mark.asyncio
async def test_task_creation_notifies_assigned_owner(
    collaboration_context: CollaborationContext,
) -> None:
    ctx = collaboration_context
    service = TaskService()
    async with ctx.session_factory() as session:
        creator = await _user(session, ctx.project_owner_id)
        task = await service.create_task(
            session,
            creator,
            ctx.project_id,
            TaskCreate(title="Assigned task", owner_user_id=ctx.member_id),
        )
        task_id = task.id

    async with ctx.session_factory() as session:
        task_notifications = await _notifications_for_task(session, task_id)
        assert len(task_notifications) == 1
        assert task_notifications[0].user_id == ctx.member_id
        assert task_notifications[0].type is NotificationType.TASK_CREATED


@pytest.mark.asyncio
async def test_task_member_add_does_not_generate_notification(
    collaboration_context: CollaborationContext,
) -> None:
    ctx = collaboration_context
    service = TaskService()
    async with ctx.session_factory() as session:
        project_owner = await _user(session, ctx.project_owner_id)
        await service.add_member(
            session,
            project_owner,
            ctx.task_id,
            TaskMemberAdd(user_id=ctx.project_owner_id, role=TaskRole.COLLABORATOR),
        )

    async with ctx.session_factory() as session:
        assert await _notifications_for_task(session, ctx.task_id) == []


@pytest.mark.asyncio
async def test_task_owner_transfer_does_not_generate_notification(
    collaboration_context: CollaborationContext,
) -> None:
    ctx = collaboration_context
    service = TaskService()
    async with ctx.session_factory() as session:
        project_owner = await _user(session, ctx.project_owner_id)
        await service.transfer_owner(session, project_owner, ctx.task_id, ctx.collaborator_id)

    async with ctx.session_factory() as session:
        assert await _notifications_for_task(session, ctx.task_id) == []


@pytest.mark.asyncio
async def test_task_status_change_does_not_generate_notification(
    collaboration_context: CollaborationContext,
) -> None:
    ctx = collaboration_context
    service = TaskService()
    async with ctx.session_factory() as session:
        owner = await _user(session, ctx.member_id)
        await service.change_status(session, owner, ctx.task_id, TaskStatus.IN_PROGRESS)

    async with ctx.session_factory() as session:
        assert await _notifications_for_task(session, ctx.task_id) == []


@pytest.mark.asyncio
async def test_project_member_cannot_manage_project(
    collaboration_context: CollaborationContext,
) -> None:
    ctx = collaboration_context
    service = ProjectService()
    async with ctx.session_factory() as session:
        member = await _user(session, ctx.member_id)
        with pytest.raises(ProjectAccessDeniedError):
            await service.update_project(
                session, member, ctx.project_id, ProjectUpdate(name="Forbidden")
            )
        result = await session.execute(select(Project).where(Project.id == ctx.project_id))
        assert result.scalar_one()
