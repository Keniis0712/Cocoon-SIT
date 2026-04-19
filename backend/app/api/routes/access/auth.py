from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.access.auth import (
    LoginRequest,
    PublicFeaturesOut,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from app.schemas.common import MessageResponse


router = APIRouter()


@router.post("/login", response_model=TokenPair)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenPair:
    return db.info["container"].auth_session_service.login(db, payload.username, payload.password)


@router.post("/register", response_model=TokenPair)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> TokenPair:
    return db.info["container"].auth_session_service.register(db, payload)


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


@router.get("/features", response_model=PublicFeaturesOut)
def public_features(
    db: Session = Depends(get_db),
) -> PublicFeaturesOut:
    current = db.info["container"].system_settings_service.get_settings(db)
    allowed_models = db.info["container"].system_settings_service.list_allowed_models(db)
    return PublicFeaturesOut(
        allow_registration=current.allow_registration,
        max_chat_turns=current.max_chat_turns,
        allowed_models=allowed_models,
        rollback_retention_days=current.rollback_retention_days,
        rollback_cleanup_interval_hours=current.rollback_cleanup_interval_hours,
    )
