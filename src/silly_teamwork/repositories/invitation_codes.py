from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.invitation_code import InvitationCode


async def get_by_hash_for_update(session: AsyncSession, code_hash: str) -> InvitationCode | None:
    statement = (
        select(InvitationCode).where(InvitationCode.code_hash == code_hash).with_for_update()
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_by_hash(session: AsyncSession, code_hash: str) -> InvitationCode | None:
    result = await session.execute(
        select(InvitationCode).where(InvitationCode.code_hash == code_hash)
    )
    return result.scalar_one_or_none()


def add(session: AsyncSession, invitation: InvitationCode) -> None:
    session.add(invitation)
