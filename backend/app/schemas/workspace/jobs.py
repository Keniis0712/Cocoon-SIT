from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class WakeupRequest(BaseModel):
    cocoon_id: str
    reason: str | None = None
    run_at: datetime | None = None


class WakeupEnqueueResult(ORMModel):
    task_id: str
    job_id: str
    status: str


class DurableJobOut(ORMModel):
    id: str
    cocoon_id: str | None
    job_type: str
    status: str
    lock_key: str
    payload_json: dict
    available_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    worker_name: str | None
    error_text: str | None


class WakeupTaskOut(ORMModel):
    id: str
    cocoon_id: str
    run_at: datetime
    reason: str | None
    payload_json: dict
    status: str
    created_at: datetime


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
