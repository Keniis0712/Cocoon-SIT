from __future__ import annotations

from app.core.config import Settings
from app.services.plugins.dependency_builder import DependencyBuilder
from app.services.plugins.manager import PluginRuntimeManager
from app.services.plugins.service_access_mixin import PluginServiceAccessMixin
from app.services.plugins.service_admin_mixin import PluginServiceAdminMixin
from app.services.plugins.service_event_mixin import PluginServiceEventMixin
from app.services.plugins.service_install_mixin import PluginServiceInstallMixin
from app.services.plugins.service_user_mixin import PluginServiceUserMixin


class PluginService(
    PluginServiceAdminMixin,
    PluginServiceEventMixin,
    PluginServiceUserMixin,
    PluginServiceAccessMixin,
    PluginServiceInstallMixin,
):
    def __init__(
        self,
        *,
        settings: Settings,
        dependency_builder: DependencyBuilder,
        runtime_manager: PluginRuntimeManager,
    ) -> None:
        self.settings = settings
        self.dependency_builder = dependency_builder
        self.runtime_manager = runtime_manager


__all__ = ["PluginService"]
