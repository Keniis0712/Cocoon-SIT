import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.main import create_app
from app.models import AvailableModel, Character, Cocoon, SessionState, User
from app.worker.durable_executor import DurableJobExecutor
from app.worker.runtime import WorkerRuntime


@pytest.fixture
def tmp_path() -> Path:
    base = Path.cwd() / ".tmp_pytest"
    path = base / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        chat_dispatch_backend="memory",
        realtime_backend="memory",
        auto_create_schema=True,
        auto_seed_defaults=True,
        artifact_root=tmp_path / ".artifacts",
        secret_key="test-secret-key-for-cocoon-sit-at-least-32-bytes",
        default_admin_username="admin",
        default_admin_email="admin@example.com",
        default_admin_password="admin",
    )


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    app = create_app(test_settings)
    with TestClient(app) as test_client:
        container = test_client.app.state.container
        with container.session_factory() as session:
            admin = session.scalar(select(User).where(User.username == test_settings.default_admin_username))
            model = session.scalar(select(AvailableModel).order_by(AvailableModel.created_at.asc()))
            assert admin is not None
            assert model is not None

            character = session.scalar(select(Character).where(Character.name == "Test Character"))
            if not character:
                character = Character(
                    name="Test Character",
                    prompt_summary="Used by automated backend tests.",
                    settings_json={"visibility": "private"},
                    created_by_user_id=admin.id,
                )
                session.add(character)
                session.flush()

            cocoon = session.scalar(select(Cocoon).where(Cocoon.name == "Test Workspace"))
            if not cocoon:
                cocoon = Cocoon(
                    name="Test Workspace",
                    owner_user_id=admin.id,
                    character_id=character.id,
                    selected_model_id=model.id,
                )
                session.add(cocoon)
                session.flush()

            if not session.get(SessionState, cocoon.id):
                session.add(
                    SessionState(
                        cocoon_id=cocoon.id,
                        relation_score=0,
                        persona_json={},
                        active_tags_json=[],
                    )
                )
                session.flush()
            session.commit()
        yield test_client


@pytest.fixture
def worker_runtime(client: TestClient, test_settings: Settings) -> WorkerRuntime:
    container = client.app.state.container
    durable_executor = DurableJobExecutor(
        chat_runtime=container.chat_runtime,
        durable_jobs=container.durable_jobs,
        audit_service=container.audit_service,
        round_cleanup=container.round_cleanup,
        prompt_service=container.prompt_service,
        provider_registry=container.provider_registry,
    )
    return WorkerRuntime(
        session_factory=container.session_factory,
        chat_queue=container.chat_queue,
        chat_runtime=container.chat_runtime,
        durable_jobs=container.durable_jobs,
        durable_executor=durable_executor,
        realtime_hub=container.realtime_hub,
        worker_name=test_settings.durable_job_worker_name,
    )


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def default_cocoon_id(client: TestClient, auth_headers: dict[str, str]) -> str:
    response = client.get("/api/v1/cocoons", headers=auth_headers)
    assert response.status_code == 200, response.text
    cocoons = response.json()
    assert cocoons, "Expected at least one test cocoon"
    return cocoons[0]["id"]
