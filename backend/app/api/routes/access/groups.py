from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models import UserGroup, UserGroupMember
from app.schemas.access.groups import GroupCreate, GroupMemberCreate, GroupMemberOut, GroupOut


router = APIRouter()


@router.get("", response_model=list[GroupOut])
def list_groups(
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:read")),
) -> list[UserGroup]:
    return db.info["container"].group_service.list_groups(db)


@router.post("", response_model=GroupOut)
def create_group(
    payload: GroupCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:write")),
) -> UserGroup:
    return db.info["container"].group_service.create_group(db, payload)


@router.get("/{group_id}/members", response_model=list[GroupMemberOut])
def list_group_members(
    group_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:read")),
) -> list[UserGroupMember]:
    return db.info["container"].group_service.list_group_members(db, group_id)


@router.post("/{group_id}/members", response_model=GroupMemberOut)
def add_group_member(
    group_id: str,
    payload: GroupMemberCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:write")),
) -> UserGroupMember:
    return db.info["container"].group_service.add_group_member(db, group_id, payload)
