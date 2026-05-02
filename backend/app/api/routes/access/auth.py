from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Role, User
from app.schemas.access.auth import (
    CurrentUserOut,
    CurrentUserUpdate,
    LoginRequest,
    ImBindTokenOut,
    PublicFeaturesOut,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from app.schemas.common import MessageResponse
from app.services.security.rbac import list_permissions_for_user


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


@router.get("/me", response_model=CurrentUserOut)
def me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrentUserOut:
    role = db.get(Role, user.role_id) if user.role_id else None
    permissions = {permission: True for permission in list_permissions_for_user(db, user)}
    authorization_service = db.info["container"].authorization_service
    group_service = db.info["container"].group_service
    return CurrentUserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        role_id=user.role_id,
        primary_group_id=user.primary_group_id,
        permissions_json=user.permissions_json or {},
        timezone=user.timezone,
        role_name=role.name if role else None,
        is_active=user.is_active,
        created_at=user.created_at,
        permissions=permissions,
        primary_group_path=group_service.group_path_by_id(db, user.primary_group_id),
        is_bootstrap_admin=authorization_service.is_bootstrap_admin(user),
        has_management_console=authorization_service.has_management_console(db, user),
    )


@router.patch("/me", response_model=CurrentUserOut)
def update_me(
    payload: CurrentUserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrentUserOut:
    updated = db.info["container"].user_service.update_current_user_profile(db, user, payload)
    return me(updated, db)


@router.post("/me/im-bind-token", response_model=ImBindTokenOut)
def create_im_bind_token(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImBindTokenOut:
    token, row = db.info["container"].im_bind_token_service.issue_for_user(db, user)
    expires_at = row.expires_at.replace(tzinfo=UTC)
    expires_in_seconds = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
    return ImBindTokenOut(
        token=token,
        expires_at=expires_at,
        expires_in_seconds=expires_in_seconds,
    )


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
