import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.models import AvailableModel, SystemSettings
from app.schemas.catalog.settings import SystemSettingsUpdate
from app.services.catalog.system_settings_service import SystemSettingsService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_system_settings_service_creates_default_row_and_updates_whitelist():
    session_factory = _session_factory()
    service = SystemSettingsService(Settings())

    with session_factory() as session:
        default_row = service.get_settings(session)
        model_one = AvailableModel(provider_id="provider-1", model_name="a")
        model_two = AvailableModel(provider_id="provider-1", model_name="b")
        session.add_all([model_one, model_two])
        session.flush()

        updated = service.update_settings(
            session,
            SystemSettingsUpdate(
                allow_registration=True,
                max_chat_turns=9,
                allowed_model_ids=[model_two.id, model_one.id],
                default_max_context_messages=20,
                default_auto_compaction_enabled=False,
                private_chat_debounce_seconds=5,
                group_chat_debounce_seconds=6,
                rollback_retention_days=7,
                rollback_cleanup_interval_hours=3,
            ),
        )
        allowed = service.list_allowed_models(session)

        assert default_row.id == SystemSettingsService.DEFAULT_ROW_ID
        assert updated.allow_registration is True
        assert updated.max_chat_turns == 9
        assert updated.allowed_model_ids_json == [model_two.id, model_one.id]
        assert updated.default_max_context_messages == 20
        assert updated.default_auto_compaction_enabled is False
        assert updated.private_chat_debounce_seconds == 5
        assert updated.group_chat_debounce_seconds == 6
        assert updated.rollback_retention_days == 7
        assert updated.rollback_cleanup_interval_hours == 3
        assert [item.id for item in allowed] == [model_two.id, model_one.id]


def test_system_settings_service_validates_missing_models_and_whitelist_access():
    session_factory = _session_factory()
    service = SystemSettingsService(Settings())

    with session_factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            service.update_settings(session, SystemSettingsUpdate(allowed_model_ids=["missing"]))
        assert exc_info.value.status_code == 400

        model = AvailableModel(provider_id="provider-1", model_name="a")
        session.add(model)
        session.flush()

        service.update_settings(session, SystemSettingsUpdate(allowed_model_ids=[model.id]))
        service.require_model_allowed(session, model.id)

        with pytest.raises(HTTPException) as denied:
            service.require_model_allowed(session, "other-model")
        assert denied.value.status_code == 400

        service.update_settings(session, SystemSettingsUpdate(allowed_model_ids=[]))
        assert service.list_allowed_models(session) == []

        current = session.get(SystemSettings, SystemSettingsService.DEFAULT_ROW_ID)
        assert current is not None
