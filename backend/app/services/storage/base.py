"""Artifact storage abstraction used by the audit subsystem."""

from abc import ABC, abstractmethod


class ArtifactStore(ABC):
    """Abstract interface for writing and deleting audit artifacts."""

    @abstractmethod
    def write_text(self, relative_path: str, content: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def delete(self, relative_path: str) -> None:
        raise NotImplementedError
