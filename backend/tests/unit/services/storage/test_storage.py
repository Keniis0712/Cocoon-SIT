from pathlib import Path

import pytest

from app.services.storage.base import ArtifactStore
from app.services.storage.filesystem import FilesystemArtifactStore


def test_artifact_store_abstract_methods_raise_not_implemented():
    with pytest.raises(NotImplementedError):
        ArtifactStore.write_text(object(), "a.txt", "x")

    with pytest.raises(NotImplementedError):
        ArtifactStore.read_text(object(), "a.txt")

    with pytest.raises(NotImplementedError):
        ArtifactStore.delete(object(), "a.txt")


def test_filesystem_artifact_store_round_trips_relative_and_absolute_paths(tmp_path: Path):
    store = FilesystemArtifactStore(tmp_path / "artifacts")

    written_path = store.write_text("nested/file.txt", "hello")

    assert Path(written_path).exists()
    assert store.read_text("nested/file.txt") == "hello"
    assert store.read_text(written_path) == "hello"


def test_filesystem_artifact_store_delete_retries_until_success(tmp_path: Path, monkeypatch):
    store = FilesystemArtifactStore(tmp_path / "artifacts")
    file_path = Path(store.write_text("retry/file.txt", "hello"))
    calls = {"count": 0}

    original_unlink = Path.unlink

    def flaky_unlink(self):
        if self == file_path and calls["count"] < 2:
            calls["count"] += 1
            raise PermissionError("busy")
        return original_unlink(self)

    monkeypatch.setattr("app.services.storage.filesystem.time.sleep", lambda seconds: None)
    monkeypatch.setattr(Path, "unlink", flaky_unlink)

    store.delete(str(file_path))

    assert calls["count"] == 2
    assert file_path.exists() is False


def test_filesystem_artifact_store_delete_handles_missing_file(tmp_path: Path):
    store = FilesystemArtifactStore(tmp_path / "artifacts")

    store.delete("missing.txt")


def test_filesystem_artifact_store_delete_handles_file_not_found_and_exhausted_retries(tmp_path: Path, monkeypatch):
    store = FilesystemArtifactStore(tmp_path / "artifacts")
    file_path = store.root / "busy.txt"
    file_path.write_text("hello", encoding="utf-8")
    calls = {"count": 0}

    def missing_unlink(self):
        raise FileNotFoundError("gone")

    monkeypatch.setattr(Path, "unlink", missing_unlink)
    store.delete(str(file_path))

    monkeypatch.setattr("app.services.storage.filesystem.time.sleep", lambda seconds: None)

    def always_busy(self):
        calls["count"] += 1
        raise PermissionError("busy")

    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "unlink", always_busy)
    store.delete(str(file_path))

    assert calls["count"] == 10
