from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.models import User, UserGroup, UserGroupMember
from app.schemas.access.groups import (
    GroupCreate,
    GroupManagementGrantCreate,
    GroupManagementGrantOut,
    GroupMemberCreate,
    GroupMemberOut,
    GroupOut,
    GroupUpdate,
)


router = APIRouter()


def _serialize_group(db: Session, group: UserGroup) -> GroupOut:
    view = db.info["container"].group_service.build_group_view(db, group)
    return GroupOut.model_validate(view)


def _require_bootstrap_admin(db: Session, user: User) -> None:
    if not db.info["container"].authorization_service.is_bootstrap_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bootstrap admin required")


@router.get("", response_model=list[GroupOut])
def list_groups(
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:read")),
) -> list[GroupOut]:
    return [_serialize_group(db, group) for group in db.info["container"].group_service.list_groups(db)]


@router.post("", response_model=GroupOut)
def create_group(
    payload: GroupCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("users:write")),
) -> GroupOut:
    return _serialize_group(db, db.info["container"].group_service.create_group(db, payload, user))


@router.patch("/{group_id}", response_model=GroupOut)
def update_group(
    group_id: str,
    payload: GroupUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:write")),
) -> GroupOut:
    return _serialize_group(db, db.info["container"].group_service.update_group(db, group_id, payload))


@router.delete("/{group_id}", response_model=GroupOut)
def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:write")),
) -> GroupOut:
    return _serialize_group(db, db.info["container"].group_service.delete_group(db, group_id))


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


@router.get("/management-grants", response_model=list[GroupManagementGrantOut])
def list_management_grants(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("users:read")),
) -> list[GroupManagementGrantOut]:
    _require_bootstrap_admin(db, user)
    return db.info["container"].group_service.list_management_grants(db)


@router.post("/management-grants", response_model=GroupManagementGrantOut)
def create_management_grant(
    payload: GroupManagementGrantCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("users:write")),
) -> GroupManagementGrantOut:
    _require_bootstrap_admin(db, user)
    return db.info["container"].group_service.create_management_grant(db, payload)


@router.delete("/management-grants/{grant_id}", response_model=GroupManagementGrantOut)
def delete_management_grant(
    grant_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("users:write")),
) -> GroupManagementGrantOut:
    _require_bootstrap_admin(db, user)
    return db.info["container"].group_service.delete_management_grant(db, grant_id)
