from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models import TagRegistry, User
from app.schemas.catalog.tags import (
    TagChatGroupVisibilityOut,
    TagChatGroupVisibilityUpdate,
    TagCreate,
    TagOut,
    TagUpdate,
)
from app.services.catalog.tag_policy import (
    is_system_tag,
    list_visible_chat_group_ids,
    require_canonical_tag,
    replace_tag_visibility_groups,
)


router = APIRouter()


@router.get("", response_model=list[TagOut])
def list_tags(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tags:read")),
) -> list[TagRegistry]:
    service = db.info["container"].tag_service
    return [service.serialize_tag(db, item) for item in service.list_tags(db, user)]


@router.post("", response_model=TagOut)
def create_tag(
    payload: TagCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tags:write")),
) -> TagRegistry:
    service = db.info["container"].tag_service
    return service.serialize_tag(db, service.create_tag(db, user, payload))


@router.patch("/{tag_id}", response_model=TagOut)
def update_tag(
    tag_id: str,
    payload: TagUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tags:write")),
) -> TagRegistry:
    service = db.info["container"].tag_service
    return service.serialize_tag(db, service.update_tag(db, user, tag_id, payload))


@router.delete("/{tag_id}", response_model=TagOut)
def delete_tag(
    tag_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tags:write")),
) -> TagRegistry:
    service = db.info["container"].tag_service
    return service.serialize_tag(db, service.delete_tag(db, user, tag_id))


@router.get("/{tag_id}/chat-groups/visibility", response_model=TagChatGroupVisibilityOut)
def get_tag_chat_group_visibility(
    tag_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tags:read")),
) -> TagChatGroupVisibilityOut:
    tag = require_canonical_tag(db, tag_id, owner_user_id=user.id)
    return TagChatGroupVisibilityOut(tag_id=tag.id, chat_group_ids=list_visible_chat_group_ids(db, tag.id))


@router.put("/{tag_id}/chat-groups/visibility", response_model=TagChatGroupVisibilityOut)
def update_tag_chat_group_visibility(
    tag_id: str,
    payload: TagChatGroupVisibilityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("tags:write")),
) -> TagChatGroupVisibilityOut:
    tag = require_canonical_tag(db, tag_id, owner_user_id=user.id)
    if is_system_tag(tag):
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="System tag cannot be modified")
    return TagChatGroupVisibilityOut(
        tag_id=tag.id,
        chat_group_ids=replace_tag_visibility_groups(db, tag, payload.chat_group_ids),
    )
