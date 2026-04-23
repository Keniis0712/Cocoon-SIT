from __future__ import annotations

from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.models import Message
from app.schemas.common import AcceptedResponse
from app.schemas.workspace.cocoons import (
    ChatMessageCreate,
    ChatMessageOut,
    RetryReplyRequest,
    UserMessageEditRequest,
)
from app.services.workspace.message_dispatch_service import MessageDispatchService


router = APIRouter()


def _accepted_response_for_action(action) -> AcceptedResponse:
    debounce_until = None
    if action.debounce_until is not None:
        debounce_until = int(action.debounce_until.replace(tzinfo=timezone.utc).timestamp())
    return AcceptedResponse(action_id=action.id, status=action.status, debounce_until=debounce_until)


@router.get("/{cocoon_id}/messages", response_model=list[ChatMessageOut])
def list_messages(
    cocoon_id: str,
    before_message_id: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> list[Message]:
    db.info["container"].authorization_service.require_cocoon_access(db, user, cocoon_id, write=False)
    messages = db.info["container"].message_service.list_messages(
        db,
        cocoon_id=cocoon_id,
        before_message_id=before_message_id,
        limit=limit,
    )
    return [db.info["container"].message_service.serialize_message(message) for message in messages]


@router.post("/{cocoon_id}/messages", status_code=202, response_model=AcceptedResponse)
def send_message(
    cocoon_id: str,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> AcceptedResponse:
    db.info["container"].authorization_service.require_cocoon_access(db, user, cocoon_id, write=True)
    service: MessageDispatchService = db.info["container"].message_dispatch_service
    try:
        action = service.enqueue_chat_message(
            db,
            cocoon_id,
            content=payload.content,
            client_request_id=payload.client_request_id,
            timezone=payload.timezone,
            client_sent_at=payload.client_sent_at,
            locale=payload.locale,
            idle_seconds=payload.idle_seconds,
            recent_turn_count=payload.recent_turn_count,
            typing_hint_ms=payload.typing_hint_ms,
            sender_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _accepted_response_for_action(action)


@router.patch("/{cocoon_id}/user_message", status_code=202, response_model=AcceptedResponse)
def edit_user_message(
    cocoon_id: str,
    payload: UserMessageEditRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> AcceptedResponse:
    db.info["container"].authorization_service.require_cocoon_access(db, user, cocoon_id, write=True)
    message = db.get(Message, payload.message_id)
    if not message or message.cocoon_id != cocoon_id or message.role != "user":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User message not found")
    action = db.info["container"].message_dispatch_service.enqueue_user_message_edit(
        db,
        cocoon_id,
        message=message,
        content=payload.content,
    )
    return _accepted_response_for_action(action)


@router.post("/{cocoon_id}/reply/retry", status_code=202, response_model=AcceptedResponse)
def retry_reply(
    cocoon_id: str,
    payload: RetryReplyRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> AcceptedResponse:
    db.info["container"].authorization_service.require_cocoon_access(db, user, cocoon_id, write=True)
    action = db.info["container"].message_dispatch_service.enqueue_retry(
        db,
        cocoon_id,
        message_id=payload.message_id,
    )
    return _accepted_response_for_action(action)
