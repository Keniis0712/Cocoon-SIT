from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.workspace.plugins import (
    ChatGroupPluginConfigOut,
    ChatGroupPluginConfigUpdate,
    UserPluginConfigUpdate,
    UserPluginOut,
    UserPluginTargetBindingCreate,
    UserPluginTargetBindingOut,
)


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


@router.get("/{plugin_id}/chat-groups/{chat_group_id}/config", response_model=ChatGroupPluginConfigOut)
def get_chat_group_plugin_config(
    plugin_id: str,
    chat_group_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatGroupPluginConfigOut:
    return db.info["container"].plugin_service.get_chat_group_plugin_config(db, user, plugin_id, chat_group_id)


@router.post("/{plugin_id}/chat-groups/{chat_group_id}/enable", response_model=ChatGroupPluginConfigOut)
def enable_chat_group_plugin(
    plugin_id: str,
    chat_group_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatGroupPluginConfigOut:
    return db.info["container"].plugin_service.set_chat_group_plugin_enabled(
        db,
        user,
        plugin_id,
        chat_group_id,
        enabled=True,
    )


@router.post("/{plugin_id}/chat-groups/{chat_group_id}/disable", response_model=ChatGroupPluginConfigOut)
def disable_chat_group_plugin(
    plugin_id: str,
    chat_group_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatGroupPluginConfigOut:
    return db.info["container"].plugin_service.set_chat_group_plugin_enabled(
        db,
        user,
        plugin_id,
        chat_group_id,
        enabled=False,
    )


@router.patch("/{plugin_id}/chat-groups/{chat_group_id}/config", response_model=ChatGroupPluginConfigOut)
def update_chat_group_plugin_config(
    plugin_id: str,
    chat_group_id: str,
    payload: ChatGroupPluginConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatGroupPluginConfigOut:
    return db.info["container"].plugin_service.update_chat_group_plugin_config(
        db,
        user,
        plugin_id,
        chat_group_id,
        payload.config_json,
    )


@router.post("/{plugin_id}/chat-groups/{chat_group_id}/validate", response_model=ChatGroupPluginConfigOut)
def validate_chat_group_plugin_config(
    plugin_id: str,
    chat_group_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatGroupPluginConfigOut:
    return db.info["container"].plugin_service.validate_chat_group_plugin_config(db, user, plugin_id, chat_group_id)


@router.post("/{plugin_id}/chat-groups/{chat_group_id}/clear-error", response_model=ChatGroupPluginConfigOut)
def clear_chat_group_plugin_error(
    plugin_id: str,
    chat_group_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatGroupPluginConfigOut:
    return db.info["container"].plugin_service.clear_chat_group_plugin_error(db, user, plugin_id, chat_group_id)


@router.get("/{plugin_id}/targets", response_model=list[UserPluginTargetBindingOut])
def list_plugin_target_bindings_for_user(
    plugin_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[UserPluginTargetBindingOut]:
    return db.info["container"].plugin_service.list_target_bindings_for_user(db, user, plugin_id)


@router.post("/{plugin_id}/targets", response_model=UserPluginTargetBindingOut)
def add_plugin_target_binding_for_user(
    plugin_id: str,
    payload: UserPluginTargetBindingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserPluginTargetBindingOut:
    return db.info["container"].plugin_service.add_target_binding_for_user(
        db,
        user,
        plugin_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
    )


@router.delete("/{plugin_id}/targets/{binding_id}")
def delete_plugin_target_binding_for_user(
    plugin_id: str,
    binding_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, bool]:
    db.info["container"].plugin_service.delete_target_binding_for_user(db, user, plugin_id, binding_id)
    return {"deleted": True}
