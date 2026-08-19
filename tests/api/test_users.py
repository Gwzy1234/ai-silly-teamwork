from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from silly_teamwork.api.dependencies import get_user_service
from silly_teamwork.core.file_storage import LocalFileStorage
from silly_teamwork.core.security import create_access_token, hash_password, verify_password
from silly_teamwork.db.base import Base
from silly_teamwork.db.session import get_db_session
from silly_teamwork.main import app
from silly_teamwork.models.user import User
from silly_teamwork.services.users import UserService

pytestmark = pytest.mark.asyncio

PNG_AVATAR = b"\x89PNG\r\n\x1a\n" + b"silly-teamwork-avatar"


@dataclass(frozen=True)
class UserTestContext:
    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]
    user_id: UUID
    token: str
    upload_dir: Path


@pytest_asyncio.fixture
async def user_context(tmp_path: Path) -> AsyncIterator[UserTestContext]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    password = "current-password"
    async with session_factory.begin() as session:
        user = User(
            username="profile_user",
            email="profile@example.edu",
            display_name="Original Name",
            password_hash=hash_password(password),
        )
        session.add(user)
        await session.flush()
        user_id = user.id

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    avatar_service = UserService(
        storage=LocalFileStorage(tmp_path / "uploads"),
        max_avatar_size=1024,
    )
    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_user_service] = lambda: avatar_service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield UserTestContext(
            client=client,
            session_factory=session_factory,
            user_id=user_id,
            token=create_access_token(str(user_id)),
            upload_dir=tmp_path / "uploads",
        )

    app.dependency_overrides.clear()
    await engine.dispose()


def auth_headers(context: UserTestContext) -> dict[str, str]:
    return {"Authorization": f"Bearer {context.token}"}


class InMemoryAvatar:
    content_type = "image/png"

    def __init__(self, content: bytes) -> None:
        self._content = content

    async def read(self, size: int = -1) -> bytes:
        content, self._content = self._content, b""
        return content


async def test_update_current_user_profile(user_context: UserTestContext) -> None:
    response = await user_context.client.patch(
        "/api/v1/users/me",
        headers=auth_headers(user_context),
        json={"nickname": "Updated Name", "bio": "  University teammate  "},
    )

    assert response.status_code == 200
    assert response.json()["nickname"] == "Updated Name"
    assert response.json()["bio"] == "University teammate"
    assert response.json()["avatar_url"] is None

    async with user_context.session_factory() as session:
        user = await session.get(User, user_context.user_id)
        assert user is not None
        assert user.display_name == "Updated Name"
        assert user.bio == "University teammate"


async def test_change_password_verifies_current_password(user_context: UserTestContext) -> None:
    wrong_response = await user_context.client.patch(
        "/api/v1/users/me/password",
        headers=auth_headers(user_context),
        json={"current_password": "wrong-password", "new_password": "new-password-123"},
    )
    assert wrong_response.status_code == 400
    assert wrong_response.json()["detail"] == "Current password is incorrect"

    response = await user_context.client.patch(
        "/api/v1/users/me/password",
        headers=auth_headers(user_context),
        json={"current_password": "current-password", "new_password": "new-password-123"},
    )
    assert response.status_code == 204

    async with user_context.session_factory() as session:
        user = await session.get(User, user_context.user_id)
        assert user is not None
        assert verify_password("new-password-123", user.password_hash)
        assert not verify_password("current-password", user.password_hash)

    old_login = await user_context.client.post(
        "/api/v1/auth/login",
        json={"username": "profile_user", "password": "current-password"},
    )
    new_login = await user_context.client.post(
        "/api/v1/auth/login",
        json={"username": "profile_user", "password": "new-password-123"},
    )
    assert old_login.status_code == 401
    assert new_login.status_code == 200


async def test_upload_read_replace_and_delete_avatar(user_context: UserTestContext) -> None:
    upload_response = await user_context.client.post(
        "/api/v1/users/me/avatar",
        headers=auth_headers(user_context),
        files={"file": ("avatar.png", PNG_AVATAR, "image/png")},
    )

    assert upload_response.status_code == 201
    public_url = upload_response.json()["avatar_url"]
    assert public_url == f"/api/v1/users/{user_context.user_id}/avatar"

    async with user_context.session_factory() as session:
        user = await session.get(User, user_context.user_id)
        assert user is not None
        assert user.avatar_url is not None
        assert user.avatar_url != public_url
        old_path = user_context.upload_dir / user.avatar_url
        assert old_path.read_bytes() == PNG_AVATAR

    read_response = await user_context.client.get(public_url)
    assert read_response.status_code == 200
    assert read_response.headers["content-type"] == "image/png"
    assert read_response.content == PNG_AVATAR

    replacement = b"\xff\xd8\xff" + b"replacement-avatar"
    replace_response = await user_context.client.post(
        "/api/v1/users/me/avatar",
        headers=auth_headers(user_context),
        files={"file": ("replacement.jpg", replacement, "image/jpeg")},
    )
    assert replace_response.status_code == 201
    assert not old_path.exists()
    assert (await user_context.client.get(public_url)).content == replacement

    delete_response = await user_context.client.delete(
        "/api/v1/users/me/avatar", headers=auth_headers(user_context)
    )
    assert delete_response.status_code == 204
    assert (await user_context.client.get(public_url)).status_code == 404
    assert list(user_context.upload_dir.rglob("*.jpg")) == []


async def test_avatar_upload_rejects_invalid_content(user_context: UserTestContext) -> None:
    response = await user_context.client.post(
        "/api/v1/users/me/avatar",
        headers=auth_headers(user_context),
        files={"file": ("not-an-image.png", b"plain text", "image/png")},
    )

    assert response.status_code == 415
    assert list(user_context.upload_dir.rglob("*.*")) == []


async def test_avatar_database_failure_cleans_new_file(
    user_context: UserTestContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = UserService(
        storage=LocalFileStorage(user_context.upload_dir),
        max_avatar_size=1024,
    )
    async with user_context.session_factory() as session:
        user = await session.get(User, user_context.user_id)
        assert user is not None

        async def fail_commit() -> None:
            raise RuntimeError("simulated database failure")

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="simulated database failure"):
            await service.upload_avatar(session, user, InMemoryAvatar(PNG_AVATAR))

    assert list(user_context.upload_dir.rglob("*.png")) == []
    async with user_context.session_factory() as session:
        user = await session.get(User, user_context.user_id)
        assert user is not None
        assert user.avatar_url is None


async def test_user_profile_endpoints_require_jwt(user_context: UserTestContext) -> None:
    profile_response = await user_context.client.patch(
        "/api/v1/users/me", json={"nickname": "No Auth"}
    )
    password_response = await user_context.client.patch(
        "/api/v1/users/me/password",
        json={"current_password": "current-password", "new_password": "new-password-123"},
    )
    avatar_response = await user_context.client.post(
        "/api/v1/users/me/avatar",
        files={"file": ("avatar.png", PNG_AVATAR, "image/png")},
    )

    assert profile_response.status_code == 401
    assert password_response.status_code == 401
    assert avatar_response.status_code == 401


async def test_openapi_documents_user_profile_contract(user_context: UserTestContext) -> None:
    schema = (await user_context.client.get("/openapi.json")).json()

    assert "patch" in schema["paths"]["/api/v1/users/me"]
    assert "/api/v1/users/me/password" in schema["paths"]
    assert "/api/v1/users/me/avatar" in schema["paths"]
    assert "/api/v1/users/{user_id}/avatar" in schema["paths"]
    assert "UserProfileUpdate" in schema["components"]["schemas"]
    assert "PasswordChangeRequest" in schema["components"]["schemas"]
