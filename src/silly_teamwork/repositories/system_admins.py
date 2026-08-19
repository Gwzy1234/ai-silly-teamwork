from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.system_admin import SystemAdmin
from silly_teamwork.models.user import User


async def get_by_user_id(session: AsyncSession, user_id: UUID) -> SystemAdmin | None:
    result = await session.execute(select(SystemAdmin).where(SystemAdmin.user_id == user_id))
    return result.scalar_one_or_none()


def add(session: AsyncSession, system_admin: SystemAdmin) -> None:
    session.add(system_admin)


async def list_with_users(session: AsyncSession) -> list[tuple[SystemAdmin, User]]:
    result = await session.execute(
        select(SystemAdmin, User)
        .join(User, User.id == SystemAdmin.user_id)
        .order_by(SystemAdmin.created_at, User.username)
    )
    return list(result.tuples().all())
