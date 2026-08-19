from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.models.ai_generation import AIGeneration
from silly_teamwork.models.enums import AIGenerationType


def add(session: AsyncSession, generation: AIGeneration) -> None:
    session.add(generation)


async def list_latest_by_type(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
) -> dict[AIGenerationType, AIGeneration]:
    """Return the most recent generation for each type for a project/user pair."""
    result = await session.execute(
        select(AIGeneration)
        .where(
            AIGeneration.project_id == project_id,
            AIGeneration.user_id == user_id,
        )
        .order_by(AIGeneration.created_at.desc(), AIGeneration.id.desc())
    )
    latest_by_type: dict[AIGenerationType, AIGeneration] = {}
    for generation in result.scalars().all():
        if generation.type not in latest_by_type:
            latest_by_type[generation.type] = generation
            if len(latest_by_type) == len(AIGenerationType):
                break
    return latest_by_type
