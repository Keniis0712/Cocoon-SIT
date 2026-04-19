from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.models import User, UserGroup, UserGroupMember
from app.schemas.access.groups import GroupCreate, GroupMemberCreate, GroupMemberOut, GroupOut, GroupUpdate


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
    user: User = Depends(get_current_user),
    _=Depends(require_permission("users:write")),
) -> UserGroup:
    return db.info["container"].group_service.create_group(db, payload, user)


@router.patch("/{group_id}", response_model=GroupOut)
def update_group(
    group_id: str,
    payload: GroupUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:write")),
) -> UserGroup:
    return db.info["container"].group_service.update_group(db, group_id, payload)


@router.delete("/{group_id}", response_model=GroupOut)
def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:write")),
) -> UserGroup:
    return db.info["container"].group_service.delete_group(db, group_id)


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


@router.delete("/{group_id}/members/{user_id}", response_model=GroupMemberOut)
def remove_group_member(
    group_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:write")),
) -> UserGroupMember:
    return db.info["container"].group_service.remove_group_member(db, group_id, user_id)
