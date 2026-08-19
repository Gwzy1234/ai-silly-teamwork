from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.user import User


async def get_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def get_by_id_for_update(session: AsyncSession, user_id: UUID) -> User | None:
    result = await session.execute(
        select(User).where(User.id == user_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


def add(session: AsyncSession, user: User) -> None:
    session.add(user)


async def list_all(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).order_by(User.created_at, User.username))
    return list(result.scalars().all())
