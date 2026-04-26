from types import SimpleNamespace

from app.models import Cocoon, PluginDefinition, PluginTargetBinding, PluginUserConfig, User
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
