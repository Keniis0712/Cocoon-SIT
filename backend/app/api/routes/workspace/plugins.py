from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.workspace.plugins import UserPluginConfigUpdate, UserPluginOut


router = APIRouter()


@router.get("", response_model=list[UserPluginOut])
def list_plugins_for_user(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[UserPluginOut]:
    return db.info["container"].plugin_service.list_plugins_for_user(db, user)


@router.get("/{plugin_id}", response_model=UserPluginOut)
def get_plugin_for_user(
    plugin_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserPluginOut:
    return db.info["container"].plugin_service.get_plugin_for_user(db, user, plugin_id)


@router.post("/{plugin_id}/enable", response_model=UserPluginOut)
def enable_plugin_for_user(
    plugin_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserPluginOut:
    return db.info["container"].plugin_service.set_plugin_enabled_for_user(
        db,
        user,
        plugin_id,
        enabled=True,
    )


@router.post("/{plugin_id}/disable", response_model=UserPluginOut)
def disable_plugin_for_user(
    plugin_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserPluginOut:
    return db.info["container"].plugin_service.set_plugin_enabled_for_user(
        db,
        user,
        plugin_id,
        enabled=False,
    )


@router.patch("/{plugin_id}/config", response_model=UserPluginOut)
def update_user_plugin_config(
    plugin_id: str,
    payload: UserPluginConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserPluginOut:
    return db.info["container"].plugin_service.update_user_plugin_config(
        db,
        user,
        plugin_id,
        payload.config_json,
    )


@router.post("/{plugin_id}/validate", response_model=UserPluginOut)
def validate_user_plugin_config(
    plugin_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserPluginOut:
    return db.info["container"].plugin_service.validate_user_plugin_config(
        db,
        user,
        plugin_id,
    )


@router.post("/{plugin_id}/clear-error", response_model=UserPluginOut)
def clear_user_plugin_error(
    plugin_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserPluginOut:
    return db.info["container"].plugin_service.clear_user_plugin_error(
        db,
        user,
        plugin_id,
    )

