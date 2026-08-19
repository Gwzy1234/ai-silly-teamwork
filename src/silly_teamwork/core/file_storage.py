from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_SAFE_SUFFIX = re.compile(r"^\.[A-Za-z0-9]{1,16}$")


@dataclass(frozen=True, slots=True)
class StoredFileTarget:
    absolute_path: Path
    storage_key: str


class LocalFileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def project_target(
        self, team_id: UUID, project_id: UUID, original_name: str
    ) -> StoredFileTarget:
        return self._target(
            Path("teams") / str(team_id) / "projects" / str(project_id) / "files",
            original_name,
        )

    def task_target(self, team_id: UUID, task_id: UUID, original_name: str) -> StoredFileTarget:
        return self._target(
            Path("teams") / str(team_id) / "tasks" / str(task_id) / "files",
            original_name,
        )

    def avatar_target(self, user_id: UUID, extension: str) -> StoredFileTarget:
        """Return a private, randomized path for a user's avatar."""

        return self._target(Path("users") / str(user_id) / "avatar", f"avatar{extension}")

    def resolve(self, storage_key: str) -> Path:
        candidate = (self.root / storage_key).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("Stored file path escapes the upload directory")
        return candidate

    def stage_delete(self, storage_key: str) -> tuple[Path, Path] | None:
        source = self.resolve(storage_key)
        if not source.is_file():
            return None
        staged = source.with_name(f".{source.name}.deleting-{uuid4().hex}")
        os.replace(source, staged)
        return source, staged

    @staticmethod
    def restore_staged_delete(staged: tuple[Path, Path] | None) -> None:
        if staged is None:
            return
        source, temporary = staged
        if temporary.exists():
            os.replace(temporary, source)

    @staticmethod
    def finish_staged_delete(staged: tuple[Path, Path] | None) -> None:
        if staged is None:
            return
        _, temporary = staged
        temporary.unlink(missing_ok=True)

    def _target(self, directory: Path, original_name: str) -> StoredFileTarget:
        suffix = Path(sanitize_filename(original_name)).suffix
        if not _SAFE_SUFFIX.fullmatch(suffix):
            suffix = ""
        relative_path = directory / f"{uuid4().hex}{suffix.lower()}"
        absolute_path = self.resolve(relative_path.as_posix())
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        return StoredFileTarget(absolute_path=absolute_path, storage_key=relative_path.as_posix())


def sanitize_filename(filename: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", filename or "")
    basename = normalized.replace("\\", "/").rsplit("/", 1)[-1]
    basename = _CONTROL_CHARACTERS.sub("", basename).strip(" .")
    if not basename or basename in {".", ".."}:
        basename = "file"
    return basename[:255]
