from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from silly_teamwork.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from silly_teamwork.models.notification import Notification
    from silly_teamwork.models.project import Project
    from silly_teamwork.models.task import Task
    from silly_teamwork.models.user import User


class File(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "files"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="size_bytes_non_negative"),
        CheckConstraint(
            "(project_id IS NOT NULL AND task_id IS NULL) "
            "OR (project_id IS NULL AND task_id IS NOT NULL)",
            name="has_exactly_one_parent",
        ),
        Index("ix_files_project_created_id", "project_id", "created_at", "id"),
        Index("ix_files_task_created_id", "task_id", "created_at", "id"),
        Index("ix_files_uploader_created_id", "uploaded_by_id", "created_at", "id"),
        Index("ix_files_created_id", "created_at", "id"),
    )

    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    uploaded_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))

    project: Mapped[Project | None] = relationship(back_populates="files")
    task: Mapped[Task | None] = relationship(back_populates="files")
    uploaded_by: Mapped[User | None] = relationship(back_populates="uploaded_files")
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="related_file", passive_deletes=True
    )
