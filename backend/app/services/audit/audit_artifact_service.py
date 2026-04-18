from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import orjson
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AuditArtifact, AuditRun, AuditStep
from app.services.storage.base import ArtifactStore


class AuditArtifactService:
    """Persists audit artifacts to storage and records their metadata."""

    def __init__(self, artifact_store: ArtifactStore, settings: Settings):
        self.artifact_store = artifact_store
        self.settings = settings

    def record_json_artifact(
        self,
        session: Session,
        run: AuditRun,
        step: AuditStep | None,
        kind: str,
        payload: dict,
        summary: str | None = None,
        metadata_json: dict | None = None,
    ) -> AuditArtifact:
        relative_path = Path("audit") / run.id / f"{kind}-{uuid4().hex}.json"
        content = orjson.dumps(payload, option=orjson.OPT_INDENT_2).decode("utf-8")
        storage_path = self.artifact_store.write_text(str(relative_path), content)
        artifact = AuditArtifact(
            run_id=run.id,
            step_id=step.id if step else None,
            kind=kind,
            storage_backend="filesystem",
            storage_path=storage_path,
            summary=summary,
            metadata_json={"relative_path": str(relative_path), **(metadata_json or {})},
            expires_at=(
                datetime.now(UTC).replace(tzinfo=None)
                + timedelta(hours=self.settings.artifact_ttl_hours)
            ),
        )
        session.add(artifact)
        session.flush()
        return artifact
