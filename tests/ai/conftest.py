from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from silly_teamwork.core.security import hash_password
from silly_teamwork.db.base import Base
from silly_teamwork.models import (
    AttachmentMode,
    File,
    Project,
    ProjectMember,
    ProjectRole,
    Task,
    TaskAssignment,
    TaskMember,
    TaskRole,
    TaskStatus,
    TaskType,
    Team,
    TeamMember,
    TeamRole,
    User,
)


@dataclass(frozen=True, slots=True)
class AIContext:
    session_factory: async_sessionmaker[AsyncSession]
    leader: User
    member: User
    outsider: User
    team: Team
    project: Project


@pytest_asyncio.fixture
async def ai_context() -> AsyncIterator[AIContext]:
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
        leader = User(username="ai_leader", password_hash=hash_password("password"))
        member = User(username="ai_member", password_hash=hash_password("password"))
        outsider = User(username="ai_outsider", password_hash=hash_password("password"))
        session.add_all([leader, member, outsider])
        await session.flush()

        team = Team(name="AI Course Team", created_by_id=leader.id)
        session.add(team)
        await session.flush()
        session.add_all(
            [
                TeamMember(team_id=team.id, user_id=leader.id, role=TeamRole.OWNER),
                TeamMember(team_id=team.id, user_id=member.id, role=TeamRole.MEMBER),
            ]
        )

        project = Project(
            team_id=team.id,
            created_by_id=leader.id,
            name="AI Course Project",
            status="active",
            starts_at=datetime.now(UTC) - timedelta(days=7),
            due_at=datetime.now(UTC) + timedelta(days=21),
        )
        session.add(project)
        await session.flush()
        session.add_all(
            [
                ProjectMember(
                    project_id=project.id,
                    user_id=leader.id,
                    role=ProjectRole.OWNER,
                ),
                ProjectMember(
                    project_id=project.id,
                    user_id=member.id,
                    role=ProjectRole.MEMBER,
                ),
            ]
        )

        task = Task(
            project_id=project.id,
            created_by_id=leader.id,
            title="Literature Review",
            description="Collect and review references",
            status=TaskStatus.TODO,
            task_type=TaskType.COLLABORATIVE,
            attachment_mode=AttachmentMode.SHARED,
            due_at=datetime.now(UTC) + timedelta(days=3),
        )
        session.add(task)
        await session.flush()
        session.add(
            TaskMember(task_id=task.id, user_id=member.id, role=TaskRole.OWNER)
        )

        personal_task = Task(
            project_id=project.id,
            created_by_id=leader.id,
            title="Weekly Reading",
            status=TaskStatus.IN_PROGRESS,
            task_type=TaskType.PERSONAL,
            attachment_mode=AttachmentMode.SHARED,
            due_at=datetime.now(UTC) + timedelta(days=5),
        )
        session.add(personal_task)
        await session.flush()
        session.add(
            TaskAssignment(
                task_id=personal_task.id,
                user_id=member.id,
                status=TaskStatus.IN_PROGRESS,
            )
        )

        session.add(
            File(
                project_id=project.id,
                uploaded_by_id=member.id,
                original_name="notes.pdf",
                storage_key="ai-notes.pdf",
                content_type="application/pdf",
                size_bytes=1024,
            )
        )

    yield AIContext(
        session_factory=factory,
        leader=leader,
        member=member,
        outsider=outsider,
        team=team,
        project=project,
    )

    await engine.dispose()
