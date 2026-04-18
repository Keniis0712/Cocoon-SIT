from typing import Literal

from pydantic import BaseModel


class DispatchQueuedEvent(BaseModel):
    type: Literal["dispatch_queued"] = "dispatch_queued"
    action_id: str
    queue_length: int


class ReplyStartedEvent(BaseModel):
    type: Literal["reply_started"] = "reply_started"
    action_id: str


class ReplyChunkEvent(BaseModel):
    type: Literal["reply_chunk"] = "reply_chunk"
    action_id: str
    text: str


class ReplyDoneEvent(BaseModel):
    type: Literal["reply_done"] = "reply_done"
    action_id: str
    final_message_id: str


class StatePatchEvent(BaseModel):
    type: Literal["state_patch"] = "state_patch"
    action_id: str
    relation_score: int
    persona_json: dict
    active_tags: list[str]
    current_wakeup_task_id: str | None


class JobStatusEvent(BaseModel):
    type: Literal["job_status"] = "job_status"
    action_id: str
    status: str


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    action_id: str
    reason: str
