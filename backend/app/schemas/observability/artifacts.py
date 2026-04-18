from pydantic import BaseModel, Field

from app.schemas.observability.audits import AuditArtifactOut


class ArtifactCleanupRequest(BaseModel):
    artifact_ids: list[str] = Field(default_factory=list)


class ArtifactListResponse(BaseModel):
    items: list[AuditArtifactOut]


class ArtifactCleanupResult(BaseModel):
    deleted: int
