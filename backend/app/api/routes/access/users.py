from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models import User
from app.schemas.access.auth import UserCreate, UserOut, UserUpdate


router = APIRouter()


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:read")),
) -> list[User]:
    return db.info["container"].user_service.list_users(db)


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:write")),
) -> User:
    return db.info["container"].user_service.create_user(db, payload)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("users:write")),
) -> User:
    return db.info["container"].user_service.update_user(db, user_id, payload)
