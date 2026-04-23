from __future__ import annotations


class PluginUserVisibleError(RuntimeError):
    """Plugin can raise this to surface a readable error on user settings."""

    def __init__(self, message: str, *, user_id: str | None = None) -> None:
        super().__init__(message)
        self.user_id = user_id

