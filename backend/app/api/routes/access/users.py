from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models import User
from app.schemas.access.auth import ManagedUserOut, UserCreate, UserUpdate
from app.services.security.rbac import get_effective_permission_map, get_role_for_user


router = APIRouter()


def _serialize_user(db: Session, user: User) -> ManagedUserOut:
    role = get_role_for_user(db, user)
    return ManagedUserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        role_id=user.role_id,
        permissions_json=user.permissions_json or {},
        timezone=user.timezone,
        role_name=role.name if role else None,
        effective_permissions=get_effective_permission_map(db, user),
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get("", response_model=list[ManagedUserOut])
def list_users(
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:read")),
) -> list[ManagedUserOut]:
    return [_serialize_user(db, user) for user in db.info["container"].user_service.list_users(db)]


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
