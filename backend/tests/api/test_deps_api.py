from types import SimpleNamespace

from app.api.deps import get_settings


def test_get_settings_returns_container_settings(test_settings):
    container = SimpleNamespace(settings=test_settings)
    assert get_settings(container) is test_settings
