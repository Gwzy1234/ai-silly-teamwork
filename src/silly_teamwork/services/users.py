from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from silly_teamwork.core.config import get_settings
from silly_teamwork.core.file_storage import LocalFileStorage
from silly_teamwork.core.security import hash_password, verify_password
from silly_teamwork.models.user import User
from silly_teamwork.repositories import users
from silly_teamwork.schemas.user import PasswordChangeRequest, UserProfileUpdate
from silly_teamwork.services.exceptions import (
    AvatarNotFoundError,
    AvatarTooLargeError,
    InvalidAvatarError,
    InvalidCurrentPasswordError,
    PasswordReuseError,
)

AVATAR_CHUNK_SIZE = 1024 * 1024
_AVATAR_FORMATS: dict[str, tuple[str, bytes]] = {
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
    "image/webp": (".webp", b"RIFF"),
}


class UploadedAvatar(Protocol):
    content_type: str | None

    async def read(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True, slots=True)
class DownloadableAvatar:
    path: Path
    content_type: str


class UserService:
    def __init__(
        self,
        storage: LocalFileStorage | None = None,
        max_avatar_size: int | None = None,
    ) -> None:
        settings = get_settings()
        self.storage = storage or LocalFileStorage(settings.upload_dir)
        self.max_avatar_size = max_avatar_size or settings.max_avatar_size

    async def update_profile(
        self,
        session: AsyncSession,
        current_user: User,
        payload: UserProfileUpdate,
    ) -> User:
        user = await self._get_locked_user(session, current_user.id)
        if "nickname" in payload.model_fields_set:
            user.display_name = payload.nickname
        if "bio" in payload.model_fields_set:
            user.bio = payload.bio
        try:
            await session.flush()
            await session.commit()
            await session.refresh(user)
        except Exception:
            await session.rollback()
            raise
        return user

    async def change_password(
        self,
        session: AsyncSession,
        current_user: User,
        payload: PasswordChangeRequest,
    ) -> None:
        user = await self._get_locked_user(session, current_user.id)
        current_password = payload.current_password.get_secret_value()
        new_password = payload.new_password.get_secret_value()
        if not verify_password(current_password, user.password_hash):
            await session.rollback()
            raise InvalidCurrentPasswordError("Current password is incorrect")
        if verify_password(new_password, user.password_hash):
            await session.rollback()
            raise PasswordReuseError("New password must be different from current password")
        try:
            user.password_hash = hash_password(new_password)
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    async def upload_avatar(
        self,
        session: AsyncSession,
        current_user: User,
        upload: UploadedAvatar,
    ) -> User:
        content_type = (upload.content_type or "").lower().split(";", 1)[0].strip()
        avatar_format = _AVATAR_FORMATS.get(content_type)
        if avatar_format is None:
            raise InvalidAvatarError("Avatar must be a JPEG, PNG, or WebP image")

        extension, _ = avatar_format
        target = self.storage.avatar_target(current_user.id, extension)
        await self._write_avatar(upload, target.absolute_path, content_type)

        old_storage_key: str | None = None
        try:
            user = await self._get_locked_user(session, current_user.id)
            old_storage_key = user.avatar_url
            user.avatar_url = target.storage_key
            await session.flush()
            await session.commit()
            await session.refresh(user)
        except Exception:
            await session.rollback()
            await asyncio.to_thread(target.absolute_path.unlink, missing_ok=True)
            raise

        if old_storage_key is not None and old_storage_key != target.storage_key:
            await self._delete_stored_avatar_best_effort(old_storage_key)
        return user

    async def delete_avatar(self, session: AsyncSession, current_user: User) -> None:
        user = await self._get_locked_user(session, current_user.id)
        old_storage_key = user.avatar_url
        if old_storage_key is None:
            raise AvatarNotFoundError("Avatar not found")
        try:
            user.avatar_url = None
            await session.flush()
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        await self._delete_stored_avatar_best_effort(old_storage_key)

    async def get_avatar(self, session: AsyncSession, user_id: UUID) -> DownloadableAvatar:
        user = await users.get_by_id(session, user_id)
        if user is None or user.avatar_url is None:
            raise AvatarNotFoundError("Avatar not found")
        try:
            path = self.storage.resolve(user.avatar_url)
        except ValueError as error:
            raise AvatarNotFoundError("Avatar not found") from error
        if not path.is_file():
            raise AvatarNotFoundError("Avatar not found")
        return DownloadableAvatar(
            path=path,
            content_type=self._content_type_from_path(path),
        )

    async def _write_avatar(
        self,
        upload: UploadedAvatar,
        destination: Path,
        content_type: str,
    ) -> None:
        total = 0
        header = bytearray()
        try:
            with destination.open("xb") as output:
                while chunk := await upload.read(AVATAR_CHUNK_SIZE):
                    total += len(chunk)
                    if total > self.max_avatar_size:
                        raise AvatarTooLargeError(
                            f"Avatar exceeds the {self.max_avatar_size}-byte size limit"
                        )
                    if len(header) < 12:
                        header.extend(chunk[: 12 - len(header)])
                    await asyncio.to_thread(output.write, chunk)
            if total == 0 or not self._matches_image_signature(bytes(header), content_type):
                raise InvalidAvatarError("Avatar content does not match its image type")
        except Exception:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise

    async def _delete_stored_avatar_best_effort(self, storage_key: str) -> None:
        try:
            path = self.storage.resolve(storage_key)
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except (OSError, ValueError):
            # The database already points at the correct state. A stale old file
            # is preferable to rolling back or corrupting that committed state.
            return

    @staticmethod
    async def _get_locked_user(session: AsyncSession, user_id: UUID) -> User:
        user = await users.get_by_id_for_update(session, user_id)
        if user is None:
            raise RuntimeError("Authenticated user no longer exists")
        return user

    @staticmethod
    def _matches_image_signature(header: bytes, content_type: str) -> bool:
        _, signature = _AVATAR_FORMATS[content_type]
        if content_type == "image/webp":
            return header.startswith(signature) and header[8:12] == b"WEBP"
        return header.startswith(signature)

    @staticmethod
    def _content_type_from_path(path: Path) -> str:
        return {
            ".jpg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(path.suffix.lower(), "application/octet-stream")


def get_user_service() -> UserService:
    return UserService()
