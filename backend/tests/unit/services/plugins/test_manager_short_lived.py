from types import SimpleNamespace

from app.models import (
    Cocoon,
    PluginDefinition,
    PluginEventDefinition,
    PluginTargetBinding,
    PluginUserConfig,
    PluginVersion,
    User,
)
from app.services.access.im_bind_token_service import ImBindTokenService
from app.services.plugins.manager import PluginRuntimeManager
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_list_short_lived_scopes_keeps_runtime_error_scopes_eligible():
    session_factory = _session_factory()
    manager = PluginRuntimeManager(
        session_factory=session_factory,
        settings=SimpleNamespace(plugin_watchdog_interval_seconds=1, plugin_short_lived_max_workers=1),
        external_wakeup_service=SimpleNamespace(),
        message_dispatch_service=SimpleNamespace(),
        im_bind_token_service=ImBindTokenService(),
    )

    with session_factory() as session:
        user = User(id="user-1", username="owner", password_hash="hash", is_active=True)
        plugin = PluginDefinition(
            id="plugin-1",
            name="plugin",
            display_name="Plugin",
            plugin_type="external",
            entry_module="main",
            status="enabled",
            is_globally_visible=True,
            user_default_config_json={"token": "seed"},
            data_dir="data/plugin",
        )
        cocoon = Cocoon(
            id="cocoon-1",
            name="Cocoon",
            owner_user_id=user.id,
            character_id="character-1",
            selected_model_id="model-1",
        )
        session.add_all([user, plugin, cocoon])
        session.add(
            PluginTargetBinding(
                plugin_id=plugin.id,
                scope_type="user",
                scope_id=user.id,
                target_type="cocoon",
                target_id=cocoon.id,
            )
        )
        session.add(
            PluginUserConfig(
                plugin_id=plugin.id,
                user_id=user.id,
                is_enabled=True,
                config_json={"token": "live"},
                runtime_error_text="timed out",
            )
        )
        session.commit()

        scopes = manager._list_short_lived_scopes(session, plugin)

    assert [(scope.scope_type, scope.scope_id, scope.user_id) for scope in scopes] == [
        ("user", "user-1", "user-1")
    ]
    assert scopes[0].timezone == "UTC"


def test_sync_plugins_uses_live_session_for_short_lived_scope_queries():
    base_factory = _session_factory()

    class _SessionProxy:
        def __init__(self, inner):
            self._inner = inner
            self.was_closed = False

        def __enter__(self):
            self._inner.__enter__()
            return self

        def __exit__(self, exc_type, exc, tb):
            self.was_closed = True
            return self._inner.__exit__(exc_type, exc, tb)

        def __getattr__(self, name):
            return getattr(self._inner, name)

    def session_factory():
        return _SessionProxy(base_factory())

    manager = PluginRuntimeManager(
        session_factory=session_factory,
        settings=SimpleNamespace(plugin_watchdog_interval_seconds=1, plugin_short_lived_max_workers=1),
        external_wakeup_service=SimpleNamespace(),
        message_dispatch_service=SimpleNamespace(),
        im_bind_token_service=ImBindTokenService(),
    )

    with base_factory() as session:
        plugin = PluginDefinition(
            id="plugin-sync-1",
            name="plugin-sync",
            display_name="Plugin Sync",
            plugin_type="external",
            entry_module="main",
            status="enabled",
            is_globally_visible=True,
            data_dir="data/plugin-sync",
            active_version_id="version-sync-1",
        )
        version = PluginVersion(
            id="version-sync-1",
            plugin_id=plugin.id,
            version="1.0.0",
            source_zip_path="plugin.zip",
            extracted_path="plugin",
            manifest_path="plugin/manifest.json",
            install_status="installed",
        )
        event = PluginEventDefinition(
            plugin_id=plugin.id,
            plugin_version_id=version.id,
            name="tick",
            mode="short_lived",
            function_name="tick",
            title="Tick",
            description="Tick event",
        )
        session.add_all([plugin, version, event])
        session.commit()

    seen_closed_flags: list[bool] = []

    def record_scopes(session, plugin):
        seen_closed_flags.append(bool(session.was_closed))
        return []

    manager._list_short_lived_scopes = record_scopes  # type: ignore[method-assign]
    manager._ensure_external_daemon = lambda *args, **kwargs: None  # type: ignore[method-assign]

    manager._sync_plugins()

    assert seen_closed_flags == [False]
