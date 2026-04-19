from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models import TagRegistry
from app.schemas.catalog.tags import TagCreate, TagOut, TagUpdate


router = APIRouter()


@router.get("", response_model=list[TagOut])
def list_tags(
    db: Session = Depends(get_db),
    _=Depends(require_permission("tags:read")),
) -> list[TagRegistry]:
    return db.info["container"].tag_service.list_tags(db)


@router.post("", response_model=TagOut)
def create_tag(
    payload: TagCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("tags:write")),
) -> TagRegistry:
    return db.info["container"].tag_service.create_tag(db, payload)


@router.patch("/{tag_id}", response_model=TagOut)
def update_tag(
    tag_id: str,
    payload: TagUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("tags:write")),
) -> TagRegistry:
    return db.info["container"].tag_service.update_tag(db, tag_id, payload)


@router.delete("/{tag_id}", response_model=TagOut)
def delete_tag(
    tag_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("tags:write")),
) -> TagRegistry:
    return db.info["container"].tag_service.delete_tag(db, tag_id)
