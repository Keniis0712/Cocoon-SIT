from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_container, get_db, require_permission
from app.core.container import AppContainer
from app.schemas.admin.plugins import (
    PluginConfigUpdate,
    PluginDetailOut,
    PluginEventConfigUpdate,
    PluginGroupVisibilityOut,
    PluginGroupVisibilityUpdate,
    PluginListItemOut,
    PluginSharedPackageOut,
    PluginVisibilityUpdate,
)

router = APIRouter()


@router.get("", response_model=list[PluginListItemOut])
def list_plugins(
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    _=Depends(require_permission("plugins:read")),
) -> list[PluginListItemOut]:
    return container.plugin_service.list_plugins(db)


@router.get("/shared-libs", response_model=list[PluginSharedPackageOut])
def list_shared_packages(
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    _=Depends(require_permission("plugins:read")),
) -> list[PluginSharedPackageOut]:
    return container.plugin_service.list_shared_packages(db)


@router.get("/{plugin_id}", response_model=PluginDetailOut)
def get_plugin(
    plugin_id: str,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    _=Depends(require_permission("plugins:read")),
) -> PluginDetailOut:
    return container.plugin_service.get_plugin_detail(db, plugin_id)


@router.post("/install", response_model=PluginDetailOut)
def install_plugin(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    _=Depends(require_permission("plugins:write")),
) -> PluginDetailOut:
    return container.plugin_service.install_plugin(db, file)


@router.post("/{plugin_id}/update", response_model=PluginDetailOut)
def update_plugin(
    plugin_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    _=Depends(require_permission("plugins:write")),
) -> PluginDetailOut:
    return container.plugin_service.update_plugin(db, plugin_id, file)


@router.post("/{plugin_id}/enable", response_model=PluginDetailOut)
def enable_plugin(
    plugin_id: str,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    _=Depends(require_permission("plugins:run")),
) -> PluginDetailOut:
    return container.plugin_service.enable_plugin(db, plugin_id)


@router.post("/{plugin_id}/disable", response_model=PluginDetailOut)
def disable_plugin(
    plugin_id: str,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    _=Depends(require_permission("plugins:run")),
) -> PluginDetailOut:
    return container.plugin_service.disable_plugin(db, plugin_id)


@router.delete("/{plugin_id}")
def delete_plugin(
    plugin_id: str,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    _=Depends(require_permission("plugins:write")),
) -> dict[str, bool]:
    container.plugin_service.delete_plugin(db, plugin_id)
    return {"deleted": True}


@router.patch("/{plugin_id}/config", response_model=PluginDetailOut)
def update_plugin_config(
    plugin_id: str,
    payload: PluginConfigUpdate,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    _=Depends(require_permission("plugins:write")),
) -> PluginDetailOut:
    return container.plugin_service.update_plugin_config(db, plugin_id, payload.config_json)


@router.patch("/{plugin_id}/events/{event_name}/config", response_model=PluginDetailOut)
def update_event_config(
    plugin_id: str,
    event_name: str,
    payload: PluginEventConfigUpdate,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    _=Depends(require_permission("plugins:write")),
) -> PluginDetailOut:
    return container.plugin_service.update_event_config(db, plugin_id, event_name, payload.config_json)


@router.post("/{plugin_id}/events/{event_name}/enable", response_model=PluginDetailOut)
def enable_event(
    plugin_id: str,
    event_name: str,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    _=Depends(require_permission("plugins:run")),
) -> PluginDetailOut:
    return container.plugin_service.set_event_enabled(db, plugin_id, event_name, True)


@router.post("/{plugin_id}/events/{event_name}/disable", response_model=PluginDetailOut)
def disable_event(
    plugin_id: str,
    event_name: str,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    _=Depends(require_permission("plugins:run")),
) -> PluginDetailOut:
    return container.plugin_service.set_event_enabled(db, plugin_id, event_name, False)


@router.patch("/{plugin_id}/visibility", response_model=PluginDetailOut)
def set_global_visibility(
    plugin_id: str,
    payload: PluginVisibilityUpdate,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    user=Depends(require_permission("plugins:write")),
) -> PluginDetailOut:
    return container.plugin_service.set_global_visibility(
        db,
        plugin_id,
        user,
        visible=payload.is_globally_visible,
    )


@router.get("/{plugin_id}/groups/visibility", response_model=list[PluginGroupVisibilityOut])
def list_group_visibility(
    plugin_id: str,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    _=Depends(require_permission("plugins:read")),
) -> list[PluginGroupVisibilityOut]:
    return container.plugin_service.list_group_visibility(db, plugin_id)


@router.put("/{plugin_id}/groups/{group_id}/visibility", response_model=PluginGroupVisibilityOut)
def set_group_visibility(
    plugin_id: str,
    group_id: str,
    payload: PluginGroupVisibilityUpdate,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    user=Depends(require_permission("plugins:write")),
) -> PluginGroupVisibilityOut:
    return container.plugin_service.set_group_visibility(
        db,
        plugin_id,
        group_id,
        user,
        visible=payload.is_visible,
    )
