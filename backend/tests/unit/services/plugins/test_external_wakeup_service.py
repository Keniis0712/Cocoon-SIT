import pytest

from app.models import (
    ChatGroupRoom,
    Cocoon,
    PluginDefinition,
    PluginDispatchRecord,
    PluginEventConfig,
    PluginGroupVisibility,
    PluginUserConfig,
    PluginVersion,
    User,
    UserGroup,
    UserGroupMember,
)
from app.services.plugins.external_wakeup_service import ExternalWakeupService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


class _SchedulerNode:
    def __init__(self):
        self.calls = []

    def schedule_wakeup(self, session, **kwargs):
        self.calls.append(kwargs)
        return type("_Task", (), {"id": "task-1"})(), object()


def test_external_wakeup_service_ignores_disabled_plugin_and_disabled_event():
    session_factory = _session_factory()
    scheduler = _SchedulerNode()
    service = ExternalWakeupService(scheduler)

    with session_factory() as session:
        plugin = PluginDefinition(
            id="plugin-1",
            name="plugin",
            display_name="Plugin",
            plugin_type="external",
            entry_module="main",
            status="disabled",
            data_dir="data/plugin",
        )
        version = PluginVersion(
            id="version-1",
            plugin_id=plugin.id,
            version="1.0.0",
            source_zip_path="plugins/plugin/source.zip",
            extracted_path="plugins/plugin/content",
            manifest_path="plugins/plugin/manifest.json",
            metadata_json={},
        )
        session.add_all([plugin, version])
        session.commit()

        assert (
            service.ingest(
                session,
                plugin=plugin,
                version=version,
                event_name="tick",
                envelope={"target_type": "cocoon", "target_id": "cocoon-1", "summary": "wake"},
            )
            is None
        )

        plugin.status = "enabled"
        session.add(PluginEventConfig(plugin_id=plugin.id, event_name="tick", is_enabled=False, config_json={}))
        session.commit()

        assert (
            service.ingest(
                session,
                plugin=plugin,
                version=version,
                event_name="tick",
                envelope={"target_type": "cocoon", "target_id": "cocoon-1", "summary": "wake"},
            )
            is None
        )
        assert scheduler.calls == []


@pytest.mark.parametrize(
    ("envelope", "message"),
    [
        ({"target_type": "unknown", "target_id": "x", "summary": "wake"}, "target_type"),
        ({"target_type": "cocoon", "summary": "wake"}, "target_id"),
        ({"target_type": "cocoon", "target_id": "x", "summary": ""}, "summary"),
    ],
)
def test_external_wakeup_service_validates_basic_envelope_fields(envelope, message):
    session_factory = _session_factory()
    scheduler = _SchedulerNode()
    service = ExternalWakeupService(scheduler)

    with session_factory() as session:
        plugin = PluginDefinition(
            id="plugin-1",
            name="plugin",
            display_name="Plugin",
            plugin_type="external",
            entry_module="main",
            status="enabled",
            data_dir="data/plugin",
        )
        version = PluginVersion(
            id="version-1",
            plugin_id=plugin.id,
            version="1.0.0",
            source_zip_path="plugins/plugin/source.zip",
            extracted_path="plugins/plugin/content",
            manifest_path="plugins/plugin/manifest.json",
            metadata_json={},
        )
        session.add_all([plugin, version])
        session.commit()

        with pytest.raises(ValueError, match=message):
            service.ingest(session, plugin=plugin, version=version, event_name="tick", envelope=envelope)


def test_external_wakeup_service_validates_targets_and_dedupes_existing_dispatch():
    session_factory = _session_factory()
    scheduler = _SchedulerNode()
    service = ExternalWakeupService(scheduler)

    with session_factory() as session:
        plugin = PluginDefinition(
            id="plugin-1",
            name="plugin",
            display_name="Plugin",
            plugin_type="external",
            entry_module="main",
            status="enabled",
            data_dir="data/plugin",
        )
        version = PluginVersion(
            id="version-1",
            plugin_id=plugin.id,
            version="1.0.0",
            source_zip_path="plugins/plugin/source.zip",
            extracted_path="plugins/plugin/content",
            manifest_path="plugins/plugin/manifest.json",
            metadata_json={},
        )
        session.add_all([plugin, version])
        session.commit()

        with pytest.raises(ValueError, match="Unknown cocoon target"):
            service.ingest(
                session,
                plugin=plugin,
                version=version,
                event_name="tick",
                envelope={"target_type": "cocoon", "target_id": "missing", "summary": "wake"},
            )

        with pytest.raises(ValueError, match="Unknown chat_group target"):
            service.ingest(
                session,
                plugin=plugin,
                version=version,
                event_name="tick",
                envelope={"target_type": "chat_group", "target_id": "missing", "summary": "wake"},
            )

        session.add(
            Cocoon(
                id="cocoon-1",
                name="Cocoon",
                owner_user_id="user-1",
                character_id="character-1",
                selected_model_id="model-1",
            )
        )
        session.add(
            PluginDispatchRecord(
                plugin_id=plugin.id,
                plugin_version_id=version.id,
                event_name="tick",
                target_type="cocoon",
                target_id="cocoon-1",
                dedupe_key="same-key",
                wakeup_task_id="existing-task",
                payload_json={},
            )
        )
        session.commit()

        assert (
            service.ingest(
                session,
                plugin=plugin,
                version=version,
                event_name="tick",
                envelope={
                    "target_type": "cocoon",
                    "target_id": "cocoon-1",
                    "summary": "wake",
                    "dedupe_key": "same-key",
                },
            )
            == "existing-task"
        )
        assert scheduler.calls == []


def test_external_wakeup_service_schedules_and_records_cocoon_and_chat_group_wakeups():
    session_factory = _session_factory()
    scheduler = _SchedulerNode()
    service = ExternalWakeupService(scheduler)

    with session_factory() as session:
        plugin = PluginDefinition(
            id="plugin-1",
            name="plugin",
            display_name="Plugin",
            plugin_type="external",
            entry_module="main",
            status="enabled",
            data_dir="data/plugin",
        )
        version = PluginVersion(
            id="version-1",
            plugin_id=plugin.id,
            version="1.0.0",
            source_zip_path="plugins/plugin/source.zip",
            extracted_path="plugins/plugin/content",
            manifest_path="plugins/plugin/manifest.json",
            metadata_json={},
        )
        cocoon = Cocoon(
            id="cocoon-1",
            name="Cocoon",
            owner_user_id="user-1",
            character_id="character-1",
            selected_model_id="model-1",
        )
        room = ChatGroupRoom(
            id="group-1",
            name="Room",
            owner_user_id="user-1",
            character_id="character-1",
            selected_model_id="model-1",
        )
        session.add_all([plugin, version, cocoon, room])
        session.commit()

        cocoon_task_id = service.ingest(
            session,
            plugin=plugin,
            version=version,
            event_name="tick",
            envelope={
                "target_type": "cocoon",
                "target_id": cocoon.id,
                "summary": "wake cocoon",
                "payload": {"kind": "cocoon"},
                "dedupe_key": 123,
            },
        )
        room_task_id = service.ingest(
            session,
            plugin=plugin,
            version=version,
            event_name="tick",
            envelope={
                "target_type": "chat_group",
                "target_id": room.id,
                "summary": "wake room",
                "payload": {"kind": "room"},
            },
        )
        records = list(session.query(PluginDispatchRecord).order_by(PluginDispatchRecord.created_at.asc()).all())

        assert cocoon_task_id == "task-1"
        assert room_task_id == "task-1"
        assert scheduler.calls[0]["cocoon_id"] == cocoon.id
        assert scheduler.calls[0]["chat_group_id"] is None
        assert scheduler.calls[0]["reason"] == "wake cocoon"
        assert scheduler.calls[0]["payload_json"]["dedupe_key"] == "123"
        assert scheduler.calls[1]["cocoon_id"] is None
        assert scheduler.calls[1]["chat_group_id"] == room.id
        assert records[0].target_type == "cocoon"
        assert records[0].payload_json["envelope"]["payload"] == {"kind": "cocoon"}
        assert records[1].target_type == "chat_group"


def test_external_wakeup_service_honors_user_visibility_enablement_and_errors():
    session_factory = _session_factory()
    scheduler = _SchedulerNode()
    service = ExternalWakeupService(scheduler)

    with session_factory() as session:
        plugin = PluginDefinition(
            id="plugin-1",
            name="plugin",
            display_name="Plugin",
            plugin_type="external",
            entry_module="main",
            status="enabled",
            is_globally_visible=False,
            data_dir="data/plugin",
        )
        version = PluginVersion(
            id="version-1",
            plugin_id=plugin.id,
            version="1.0.0",
            source_zip_path="plugins/plugin/source.zip",
            extracted_path="plugins/plugin/content",
            manifest_path="plugins/plugin/manifest.json",
            metadata_json={},
        )
        cocoon = Cocoon(
            id="cocoon-1",
            name="Cocoon",
            owner_user_id="user-1",
            character_id="character-1",
            selected_model_id="model-1",
        )
        owner = User(id="user-1", username="owner", password_hash="hash", is_active=True)
        group = UserGroup(id="group-1", name="G1", owner_user_id="user-1")
        session.add_all([owner, group, plugin, version, cocoon])
        session.commit()

        hidden_result = service.ingest(
            session,
            plugin=plugin,
            version=version,
            event_name="tick",
            envelope={
                "target_type": "cocoon",
                "target_id": cocoon.id,
                "summary": "wake cocoon",
            },
        )
        assert hidden_result is None
        assert scheduler.calls == []

        session.add(UserGroupMember(group_id="group-1", user_id="user-1", member_role="member"))
        session.add(PluginGroupVisibility(plugin_id=plugin.id, group_id="group-1", is_visible=True))
        session.commit()
        visible_result = service.ingest(
            session,
            plugin=plugin,
            version=version,
            event_name="tick",
            envelope={
                "target_type": "cocoon",
                "target_id": cocoon.id,
                "summary": "wake cocoon",
            },
        )
        assert visible_result == "task-1"

        user_config = PluginUserConfig(
            plugin_id=plugin.id,
            user_id="user-1",
            is_enabled=False,
            config_json={},
        )
        session.add(user_config)
        session.commit()
        assert (
            service.ingest(
                session,
                plugin=plugin,
                version=version,
                event_name="tick",
                envelope={
                    "target_type": "cocoon",
                    "target_id": cocoon.id,
                    "summary": "wake cocoon",
                },
            )
            is None
        )

        user_config.is_enabled = True
        user_config.error_text = "api key invalid"
        session.commit()
        assert (
            service.ingest(
                session,
                plugin=plugin,
                version=version,
                event_name="tick",
                envelope={
                    "target_type": "cocoon",
                    "target_id": cocoon.id,
                    "summary": "wake cocoon",
                },
            )
            is None
        )
