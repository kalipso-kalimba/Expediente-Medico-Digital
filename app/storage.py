"""Centralized storage abstraction for Expediente Medico Digital.

Provides a unified interface for file operations, supporting local
filesystem paths and NAS-mounted paths via configurable backends.
"""

import os
import shutil
from pathlib import Path

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local_path")
STORAGE_ROOT = os.getenv("STORAGE_ROOT", "")
PATIENT_FILES_ROOT = os.getenv("PATIENT_FILES_ROOT", "Expediente de pacientes")
INCOMPLETE_FILES_ROOT = "formularios_incompletos"
BACKUPS_ROOT = "backups"
LOGS_ROOT = "logs"
TMP_ROOT = "tmp"


class StorageError(IOError):
    """Raised when a storage operation fails."""


class LocalPathStorageBackend:
    """Stores files on a local or network-mounted path.

    Relative keys are resolved against the configured root directory.
    Absolute keys (legacy data) are used as-is with security validation.
    """

    def __init__(self, root: str):
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _resolve_key(self, key: str) -> Path:
        p = Path(key)
        if p.is_absolute():
            resolved = p.resolve()
            if self._root not in resolved.parents and resolved != self._root:
                if resolved.drive != self._root.drive:
                    raise StorageError(f"Path traversal detected: {key}")
            return resolved
        resolved = (self._root / key).resolve()
        if self._root not in resolved.parents and resolved != self._root:
            if not str(resolved).startswith(str(self._root)):
                raise StorageError(f"Path traversal detected: {key}")
        return resolved

    def save(self, key: str, data: bytes) -> None:
        path = self._resolve_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def save_fileobj(self, key: str, source, max_size: int = 0) -> None:
        path = self._resolve_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as out:
            shutil.copyfileobj(source, out)
        if max_size and path.stat().st_size > max_size:
            path.unlink(missing_ok=True)
            raise StorageError(f"File exceeds maximum size of {max_size} bytes")

    def read(self, key: str) -> bytes:
        path = self._resolve_key(key)
        return path.read_bytes()

    def open(self, key: str, mode: str = "rb"):
        path = self._resolve_key(key)
        return path.open(mode)

    def delete(self, key: str) -> bool:
        path = self._resolve_key(key)
        if path.exists() and path.is_file():
            path.unlink()
            return True
        return False

    def exists(self, key: str) -> bool:
        return self._resolve_key(key).exists()

    def is_dir(self, key: str) -> bool:
        return self._resolve_key(key).is_dir()

    def mkdir(self, key: str) -> None:
        self._resolve_key(key).mkdir(parents=True, exist_ok=True)

    def rmdir(self, key: str) -> bool:
        path = self._resolve_key(key)
        if path.exists() and path.is_dir():
            shutil.rmtree(str(path))
            return True
        return False

    def move(self, old_key: str, new_key: str) -> None:
        src = self._resolve_key(old_key)
        dst = self._resolve_key(new_key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

    def copy(self, old_key: str, new_key: str) -> None:
        src = self._resolve_key(old_key)
        dst = self._resolve_key(new_key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
        else:
            shutil.copy2(str(src), str(dst))

    def resolve(self, key: str) -> Path:
        return self._resolve_key(key)

    def list_dir(self, key: str) -> list[dict]:
        path = self._resolve_key(key)
        if not path.is_dir():
            return []
        items = []
        for entry in sorted(path.iterdir()):
            items.append(
                {
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": entry.stat().st_size if entry.is_file() else 0,
                }
            )
        return items

    def iterdir(self, key: str):
        path = self._resolve_key(key)
        if path.is_dir():
            return list(path.iterdir())
        return []

    def move_to(self, key: str, destination_dir_key: str) -> str | None:
        src = self._resolve_key(key)
        if not src.exists():
            return None
        dst_dir = self._resolve_key(destination_dir_key)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = self._available_path(dst_dir / src.name)
        shutil.move(str(src), str(dst))
        return str(self._relative_key(dst))

    def _available_path(self, path: Path) -> Path:
        if not path.exists():
            return path
        for index in range(2, 1000):
            candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
            if not candidate.exists():
                return candidate
        raise StorageError("No se pudo crear un nombre de archivo disponible")

    def _relative_key(self, path: Path) -> str:
        try:
            return str(path.relative_to(self._root))
        except ValueError:
            return str(path)


def _resolve_storage_root() -> str:
    root = STORAGE_ROOT.strip()
    if root:
        return root
    from pathlib import Path as _Path

    base = _Path(__file__).resolve().parent.parent
    return str(base / "storage")


_backend_instance: LocalPathStorageBackend | None = None


def get_storage_backend() -> LocalPathStorageBackend:
    global _backend_instance
    if _backend_instance is None:
        _backend_instance = LocalPathStorageBackend(_resolve_storage_root())
    return _backend_instance


storage = get_storage_backend()
