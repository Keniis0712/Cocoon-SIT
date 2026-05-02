from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models import User
from app.schemas.access.auth import ManagedUserOut, UserCreate, UserUpdate
from app.services.security.rbac import get_effective_permission_map, get_role_for_user


router = APIRouter()


def _serialize_user(db: Session, user: User) -> ManagedUserOut:
    role = get_role_for_user(db, user)
    authorization_service = db.info["container"].authorization_service
    group_service = db.info["container"].group_service
    return ManagedUserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        role_id=user.role_id,
        primary_group_id=user.primary_group_id,
        permissions_json=user.permissions_json or {},
        timezone=user.timezone,
        role_name=role.name if role else None,
        effective_permissions=get_effective_permission_map(db, user),
        is_active=user.is_active,
        created_at=user.created_at,
        primary_group_path=group_service.group_path_by_id(db, user.primary_group_id),
        is_bootstrap_admin=authorization_service.is_bootstrap_admin(user),
        has_management_console=authorization_service.has_management_console(db, user),
    )


@router.get("", response_model=list[ManagedUserOut])
def list_users(
    scope: Literal["all", "manageable"] = "all",
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("users:read")),
) -> list[ManagedUserOut]:
    if scope == "manageable":
        manageable_ids = set(db.info["container"].authorization_service.list_manageable_user_ids(db, user))
        items = list(
            db.scalars(select(User).where(User.id.in_(manageable_ids)).order_by(User.created_at.asc())).all()
        )
    else:
        items = db.info["container"].user_service.list_users(db)
    return [_serialize_user(db, item) for item in items]


@router.post("", response_model=ManagedUserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:write")),
) -> ManagedUserOut:
    user = db.info["container"].user_service.create_user(db, payload)
    return _serialize_user(db, user)


@router.patch("/{user_id}", response_model=ManagedUserOut)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("users:write")),
) -> ManagedUserOut:
    updated = db.info["container"].user_service.update_user(db, user, user_id, payload)
    return _serialize_user(db, updated)
