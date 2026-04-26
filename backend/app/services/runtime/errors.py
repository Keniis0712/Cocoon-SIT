from __future__ import annotations


class RuntimeActionAbortedError(RuntimeError):
    """Raised when an action is no longer allowed to persist runtime side effects."""
