from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app, dump_openapi


def test_create_app_binds_container_lifespan_and_optional_cors(monkeypatch, tmp_path):
    calls = []

    class _ConnectionManager:
        def bind_loop(self, loop):
            calls.append(("bind_loop", loop.__class__.__name__))

    class _Container:
        def __init__(self, settings):
            self.settings = settings
            self.connection_manager = _ConnectionManager()

        def initialize(self):
            calls.append("initialize")

        def shutdown(self):
            calls.append("shutdown")

    monkeypatch.setattr("app.main.configure_logging", lambda: calls.append("logging"))
    monkeypatch.setattr("app.main.AppContainer", _Container)
    monkeypatch.setattr("app.main.mount_frontend", lambda app, path: calls.append(("mount_frontend", Path(path))))

    settings = Settings(
        cors_origins=["https://example.com"],
        frontend_dist_path=tmp_path / "frontend-dist",
    )
    app = create_app(settings)

    assert app.state.container.settings is settings
    assert any(m.cls.__name__ == "CORSMiddleware" for m in app.user_middleware)
    assert ("mount_frontend", settings.frontend_dist_path) in calls

    with TestClient(app):
        pass

    assert calls[0] == "logging"
    assert "initialize" in calls
    assert "shutdown" in calls
    assert any(call[0] == "bind_loop" for call in calls if isinstance(call, tuple))


def test_dump_openapi_writes_schema_to_configured_path(monkeypatch, tmp_path):
    output_path = tmp_path / "openapi" / "schema.json"
    fake_app = SimpleNamespace(openapi=lambda: {"openapi": "3.1.0", "info": {"title": "Test"}})
    settings = Settings(dump_openapi_path=str(output_path))

    monkeypatch.setattr("app.main.create_app", lambda provided_settings=None: fake_app)

    written = dump_openapi(settings)

    assert written == output_path
    assert output_path.exists()
    assert '"openapi": "3.1.0"' in output_path.read_text(encoding="utf-8")
