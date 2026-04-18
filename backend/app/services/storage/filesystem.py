import time
from pathlib import Path

from app.services.storage.base import ArtifactStore


class FilesystemArtifactStore(ArtifactStore):
    """Stores audit artifacts on the local filesystem."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def write_text(self, relative_path: str, content: str) -> str:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)

    def delete(self, relative_path: str) -> None:
        path = Path(relative_path)
        if not path.is_absolute():
            path = self.root / relative_path
        for _ in range(10):
            try:
                if path.exists():
                    path.unlink()
                return
            except FileNotFoundError:
                return
            except (PermissionError, OSError):
                time.sleep(0.05)
        return
