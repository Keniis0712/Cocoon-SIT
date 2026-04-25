from datetime import datetime
from typing import Any

from app.schemas.common import ORMModel


class AuditArtifactOut(ORMModel):
    id: str
    kind: str
    storage_backend: str
    storage_path: str | None
    summary: str | None
    metadata_json: dict
    payload_json: Any = None
    expires_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime


class AuditStepOut(ORMModel):
    id: str
    step_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    meta_json: dict


class AuditRunOut(ORMModel):
    id: str
    cocoon_id: str | None
    chat_group_id: str | None = None
    action_id: str | None
    user_message_id: str | None = None
    assistant_message_id: str | None = None
    trigger_input: str | None = None
    assistant_output: str | None = None
    operation_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None


class AuditLinkOut(ORMModel):
    id: str
    source_artifact_id: str | None
    source_step_id: str | None
    target_artifact_id: str | None
    target_step_id: str | None
    relation: str
    created_at: datetime


class AuditRunDetail(ORMModel):
    run: AuditRunOut
    steps: list[AuditStepOut]
    artifacts: list[AuditArtifactOut]
    links: list[AuditLinkOut]
