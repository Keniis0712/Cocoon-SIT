from __future__ import annotations

from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, WebSocketException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.api.wakeup_serialization import serialize_wakeup_task
from app.models import (
    ActionDispatch,
    AuditArtifact,
    AuditLink,
    AuditRun,
    AuditStep,
    ChatGroupMember,
    ChatGroupRoom,
    DurableJob,
    FailedRound,
    MemoryChunk,
    MemoryEmbedding,
    MemoryTag,
    Message,
    MessageTag,
    User,
    WakeupTask,
)
from app.schemas.common import AcceptedResponse
from app.schemas.observability.wakeups import WakeupTaskOut
from app.schemas.workspace.chat_groups import (
    ChatGroupMemberCreate,
    ChatGroupMemberOut,
    ChatGroupMemberUpdate,
    ChatGroupRoomCreate,
    ChatGroupRoomOut,
    ChatGroupRoomUpdate,
    ChatGroupStateOut,
    MessageRetractResult,
)
from app.schemas.workspace.cocoons import ChatMessageCreate, ChatMessageOut
from app.services.runtime.wakeup_tasks import list_wakeup_tasks
from app.services.workspace.targets import get_session_state


router = APIRouter()


def _accepted_response_for_action(action) -> AcceptedResponse:
    debounce_until = None
    if action.debounce_until is not None:
        debounce_until = int(action.debounce_until.replace(tzinfo=UTC).timestamp())
    return AcceptedResponse(action_id=action.id, status=action.status, debounce_until=debounce_until)


def _cleanup_room(session: Session, room_id: str) -> None:
    action_ids = list(
        session.scalars(select(ActionDispatch.id).where(ActionDispatch.chat_group_id == room_id)).all()
    )
    audit_run_ids = list(session.scalars(select(AuditRun.id).where(AuditRun.chat_group_id == room_id)).all())
    step_ids = list(session.scalars(select(AuditStep.id).where(AuditStep.run_id.in_(audit_run_ids))).all()) if audit_run_ids else []
    message_ids = list(session.scalars(select(Message.id).where(Message.chat_group_id == room_id)).all())
    memory_ids = list(session.scalars(select(MemoryChunk.id).where(MemoryChunk.chat_group_id == room_id)).all())
    durable_job_ids = list(session.scalars(select(DurableJob.id).where(DurableJob.chat_group_id == room_id)).all())

    session.query(WakeupTask).filter(WakeupTask.chat_group_id == room_id).delete(synchronize_session=False)
    session.query(DurableJob).filter(DurableJob.id.in_(durable_job_ids)).delete(synchronize_session=False)

    if memory_ids:
        session.query(MemoryTag).filter(MemoryTag.memory_chunk_id.in_(memory_ids)).delete(synchronize_session=False)
        session.query(MemoryEmbedding).filter(MemoryEmbedding.memory_chunk_id.in_(memory_ids)).delete(
            synchronize_session=False
        )
        session.query(MemoryChunk).filter(MemoryChunk.id.in_(memory_ids)).delete(synchronize_session=False)

    if message_ids:
        session.query(MessageTag).filter(MessageTag.message_id.in_(message_ids)).delete(synchronize_session=False)
        session.query(Message).filter(Message.id.in_(message_ids)).delete(synchronize_session=False)

    if step_ids:
        session.query(AuditLink).filter(
            (AuditLink.source_step_id.in_(step_ids)) | (AuditLink.target_step_id.in_(step_ids))
        ).delete(synchronize_session=False)

    if audit_run_ids:
        artifact_ids = list(session.scalars(select(AuditArtifact.id).where(AuditArtifact.run_id.in_(audit_run_ids))).all())
        if artifact_ids:
            session.query(AuditLink).filter(
                (AuditLink.source_artifact_id.in_(artifact_ids)) | (AuditLink.target_artifact_id.in_(artifact_ids))
            ).delete(synchronize_session=False)
            session.query(AuditArtifact).filter(AuditArtifact.id.in_(artifact_ids)).delete(synchronize_session=False)
        session.query(AuditStep).filter(AuditStep.run_id.in_(audit_run_ids)).delete(synchronize_session=False)
        session.query(AuditRun).filter(AuditRun.id.in_(audit_run_ids)).delete(synchronize_session=False)

    if action_ids:
        session.query(FailedRound).filter(
            (FailedRound.chat_group_id == room_id) | (FailedRound.action_id.in_(action_ids))
        ).delete(synchronize_session=False)
        session.query(ActionDispatch).filter(ActionDispatch.id.in_(action_ids)).delete(synchronize_session=False)
    else:
        session.query(FailedRound).filter(FailedRound.chat_group_id == room_id).delete(synchronize_session=False)

    state = get_session_state(session, chat_group_id=room_id)
    if state:
        session.delete(state)
    session.query(ChatGroupMember).filter(ChatGroupMember.room_id == room_id).delete(synchronize_session=False)
    session.flush()


@router.get("", response_model=list[ChatGroupRoomOut])
def list_chat_groups(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> list[ChatGroupRoom]:
    rooms = db.info["container"].chat_group_service.list_rooms(db)
    return db.info["container"].authorization_service.filter_visible_chat_groups(db, user, rooms)


@router.post("", response_model=ChatGroupRoomOut)
def create_chat_group(
    payload: ChatGroupRoomCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> ChatGroupRoom:
    db.info["container"].authorization_service.require_character_use(db, user, payload.character_id)
    room = db.info["container"].chat_group_service.create_room(db, payload, user)
    return room


@router.get("/{room_id}", response_model=ChatGroupRoomOut)
def get_chat_group(
    room_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> ChatGroupRoom:
    return db.info["container"].authorization_service.require_chat_group_access(db, user, room_id)


@router.patch("/{room_id}", response_model=ChatGroupRoomOut)
def update_chat_group(
    room_id: str,
    payload: ChatGroupRoomUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> ChatGroupRoom:
    room = db.info["container"].authorization_service.require_chat_group_access(db, user, room_id, manage=True)
    if payload.character_id is not None:
        db.info["container"].authorization_service.require_character_use(db, user, payload.character_id)
    return db.info["container"].chat_group_service.update_room(db, room, payload)


@router.delete("/{room_id}", response_model=ChatGroupRoomOut)
def delete_chat_group(
    room_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> ChatGroupRoom:
    room = db.info["container"].authorization_service.require_chat_group_access(db, user, room_id, owner=True)
    _cleanup_room(db, room_id)
    return db.info["container"].chat_group_service.delete_room(db, room)


@router.get("/{room_id}/members", response_model=list[ChatGroupMemberOut])
def list_chat_group_members(
    room_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> list[ChatGroupMember]:
    db.info["container"].authorization_service.require_chat_group_access(db, user, room_id)
    return db.info["container"].chat_group_service.list_members(db, room_id)


@router.post("/{room_id}/members", response_model=ChatGroupMemberOut)
def add_chat_group_member(
    room_id: str,
    payload: ChatGroupMemberCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> ChatGroupMember:
    room = db.info["container"].authorization_service.require_chat_group_access(db, user, room_id, manage=True)
    return db.info["container"].chat_group_service.add_member(db, room, payload)


@router.patch("/{room_id}/members/{user_id}", response_model=ChatGroupMemberOut)
def update_chat_group_member(
    room_id: str,
    user_id: str,
    payload: ChatGroupMemberUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> ChatGroupMember:
    room = db.info["container"].authorization_service.require_chat_group_access(db, user, room_id, manage=True)
    return db.info["container"].chat_group_service.update_member(db, room, user_id, payload)


@router.delete("/{room_id}/members/{user_id}", response_model=ChatGroupMemberOut)
def remove_chat_group_member(
    room_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> ChatGroupMember:
    room = db.info["container"].authorization_service.require_chat_group_access(db, user, room_id, manage=True)
    return db.info["container"].chat_group_service.remove_member(db, room, user_id)


@router.get("/{room_id}/messages", response_model=list[ChatMessageOut])
def list_chat_group_messages(
    room_id: str,
    before_message_id: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> list[ChatMessageOut]:
    db.info["container"].authorization_service.require_chat_group_access(db, user, room_id)
    messages = db.info["container"].message_service.list_messages(
        db,
        chat_group_id=room_id,
        before_message_id=before_message_id,
        limit=limit,
    )
    return [db.info["container"].message_service.serialize_message(message) for message in messages]


@router.post("/{room_id}/messages", status_code=202, response_model=AcceptedResponse)
def send_chat_group_message(
    room_id: str,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> AcceptedResponse:
    db.info["container"].authorization_service.require_chat_group_access(db, user, room_id, write=True)
    action = db.info["container"].message_dispatch_service.enqueue_chat_group_message(
        db,
        room_id,
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
    return _accepted_response_for_action(action)


@router.post("/{room_id}/messages/{message_id}/retract", response_model=MessageRetractResult)
def retract_chat_group_message(
    room_id: str,
    message_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> MessageRetractResult:
    container: AppContainer = db.info["container"]
    room = container.authorization_service.require_chat_group_access(db, user, room_id, write=True)
    message = container.message_service.require_message_for_target(db, message_id, chat_group_id=room_id)
    can_manage = container.authorization_service.can_manage_chat_group(db, user, room)
    if message.role == "user":
        if message.sender_user_id != user.id and not can_manage:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot retract this message")
    elif not can_manage:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot retract AI message")
    message = container.message_service.retract_message(
        db,
        message,
        acting_user_id=user.id,
        note="Message retracted",
    )
    return MessageRetractResult(
        message_id=message.id,
        is_retracted=message.is_retracted,
        retracted_at=message.retracted_at,
        retracted_by_user_id=message.retracted_by_user_id,
        retraction_note=message.retraction_note,
    )


@router.get("/{room_id}/state", response_model=ChatGroupStateOut)
def get_chat_group_state(
    room_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> ChatGroupStateOut:
    db.info["container"].authorization_service.require_chat_group_access(db, user, room_id)
    state = get_session_state(db, chat_group_id=room_id)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session state not found")
    return ChatGroupStateOut.model_validate(state)


@router.get("/{room_id}/wakeups", response_model=list[WakeupTaskOut])
def list_chat_group_wakeups(
    room_id: str,
    status: str | None = None,
    only_ai: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> list[WakeupTaskOut]:
    db.info["container"].authorization_service.require_chat_group_access(db, user, room_id)
    tasks = list_wakeup_tasks(
        db,
        chat_group_id=room_id,
        status=status,
        only_ai=only_ai,
        limit=limit,
    )
    return [serialize_wakeup_task(db, task) for task in tasks]


@router.websocket("/{room_id}/ws")
async def chat_group_ws(websocket: WebSocket, room_id: str) -> None:
    container = websocket.app.state.container
    try:
        await container.workspace_realtime_service.connect_authenticated(
            websocket,
            room_id,
            "cocoons:read",
            target_type="chat_group",
        )
    except WebSocketException as exc:
        await websocket.close(code=exc.code)
        return
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        container.workspace_realtime_service.disconnect(room_id, websocket, target_type="chat_group")
