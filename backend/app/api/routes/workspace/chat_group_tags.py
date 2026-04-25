from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.models import ChatGroupTagBinding
from app.schemas.workspace.cocoons import CocoonTagBindRequest
from app.schemas.workspace.tags import ChatGroupTagBindingOut, ChatGroupTagBindResult


router = APIRouter()


@router.get("/{room_id}/tags", response_model=list[ChatGroupTagBindingOut])
def list_chat_group_tags(
    room_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> list[ChatGroupTagBinding]:
    db.info["container"].authorization_service.require_chat_group_access(db, user, room_id)
    return list(
        db.scalars(
            select(ChatGroupTagBinding)
            .where(ChatGroupTagBinding.chat_group_id == room_id)
            .order_by(ChatGroupTagBinding.created_at.asc())
        ).all()
    )


@router.post("/{room_id}/tags", response_model=ChatGroupTagBindResult)
def bind_chat_group_tag(
    room_id: str,
    payload: CocoonTagBindRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> ChatGroupTagBindResult:
    db.info["container"].authorization_service.require_chat_group_access(db, user, room_id, write=True)
    binding = db.info["container"].chat_group_tag_service.bind_tag(db, room_id, payload.tag_id)
    return ChatGroupTagBindResult(binding_id=binding.id, tag_id=binding.tag_id)


@router.delete("/{room_id}/tags/{tag_id}", response_model=ChatGroupTagBindResult)
def unbind_chat_group_tag(
    room_id: str,
    tag_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> ChatGroupTagBindResult:
    db.info["container"].authorization_service.require_chat_group_access(db, user, room_id, write=True)
    binding = db.info["container"].chat_group_tag_service.unbind_tag(db, room_id, tag_id)
    return ChatGroupTagBindResult(binding_id=binding.id, tag_id=binding.tag_id)
