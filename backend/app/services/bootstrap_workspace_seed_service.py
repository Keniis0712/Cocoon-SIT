from __future__ import annotations

from sqlalchemy.orm import Session

class BootstrapWorkspaceSeedService:
    """Reserved hook for workspace seeding.

    The current product no longer creates a default workspace implicitly.
    """

    def ensure_defaults(
        self,
        session: Session,
        *,
        owner_user_id: str,
        character_id: str,
        model_id: str,
    ) -> None:
        del session, owner_user_id, character_id, model_id
        return None
