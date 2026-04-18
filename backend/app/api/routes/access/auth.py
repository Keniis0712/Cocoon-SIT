from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.access.auth import LoginRequest, RefreshRequest, TokenPair, UserOut
from app.schemas.common import MessageResponse


router = APIRouter()


@router.post("/login", response_model=TokenPair)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenPair:
    return db.info["container"].auth_session_service.login(db, payload.username, payload.password)


@router.post("/refresh", response_model=TokenPair)
def refresh(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
) -> TokenPair:
    return db.info["container"].auth_session_service.refresh(db, payload.refresh_token)


@router.post("/logout", response_model=MessageResponse)
def logout(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    return db.info["container"].auth_session_service.logout(db, payload.refresh_token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
