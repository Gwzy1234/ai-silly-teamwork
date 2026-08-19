from __future__ import annotations

import asyncio
import sys

from silly_teamwork.core.config import get_settings
from silly_teamwork.db.session import AsyncSessionFactory, engine
from silly_teamwork.models.enums import InvitationStatus
from silly_teamwork.services.seed import DevelopmentSeedService, SeedRequest


async def seed_database() -> int:
    settings = get_settings()
    if settings.environment != "development":
        print("Seed refused: ENVIRONMENT must be development.", file=sys.stderr)
        return 2

    invite_code = settings.seed_invite_code.get_secret_value()
    request = SeedRequest(
        admin_username=settings.seed_admin_username,
        admin_password=settings.seed_admin_password.get_secret_value(),
        admin_nickname=settings.seed_admin_nickname,
        team_name=settings.seed_team_name,
        invite_code=invite_code,
    )

    try:
        async with AsyncSessionFactory() as session:
            result = await DevelopmentSeedService().run(session, request)
    finally:
        await engine.dispose()

    print("Silly Teamwork development seed completed.")
    print(f"Admin username: {request.admin_username}")
    print(f"Admin password: {request.admin_password}")
    print(f"Team: {request.team_name}")
    print(f"Invitation code: {invite_code}")
    print(f"Invitation status: {result.invitation_status.value}")
    if result.invitation_status is not InvitationStatus.ACTIVE:
        print(
            "Warning: the stored invitation has already been consumed or disabled; "
            "change SEED_INVITE_CODE to create another test code.",
            file=sys.stderr,
        )
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(seed_database()))


if __name__ == "__main__":
    main()
