from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel

class DurableJobOut(ORMModel):
    id: str
    cocoon_id: str | None
    chat_group_id: str | None = None
    job_type: str
    status: str
    lock_key: str
    payload_json: dict
    available_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    worker_name: str | None
    error_text: str | None

class PullJobOut(ORMModel):
    id: str
    durable_job_id: str
    source_cocoon_id: str
    target_cocoon_id: str
    status: str
    summary_json: dict
    created_at: datetime


class PullRequest(BaseModel):
    source_cocoon_id: str
    target_cocoon_id: str


class PullEnqueueResult(ORMModel):
    job_id: str
    pull_job_id: str
    status: str


class MergeJobOut(ORMModel):
    id: str
    durable_job_id: str
    source_cocoon_id: str
    target_cocoon_id: str
    status: str
    summary_json: dict
    created_at: datetime


class MergeRequest(BaseModel):
    source_cocoon_id: str
    target_cocoon_id: str


class MergeEnqueueResult(ORMModel):
    job_id: str
    merge_job_id: str
    status: str
