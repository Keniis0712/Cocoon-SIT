import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.core.container import AppContainer
from app.main import create_app
from app.models import Base, AvailableModel, Character, ChatGroupRoom, MemoryChunk, ModelProvider, User
from app.schemas.catalog.embedding_providers import EmbeddingProviderCreate
from app.worker.durable_executor import DurableJobExecutor
from app.worker.runtime import WorkerRuntime


def _pgvector_database_url() -> str | None:
    return os.getenv("COCOON_PGVECTOR_TEST_DATABASE_URL")


def _ensure_mock_chat_model(session) -> AvailableModel:
    model = session.scalar(select(AvailableModel).where(AvailableModel.model_name == "pgvector-runtime-mock-model"))
    if model is not None:
        return model
    provider = session.scalar(select(ModelProvider).where(ModelProvider.name == "pgvector-runtime-mock"))
    if provider is None:
        provider = ModelProvider(
            name="pgvector-runtime-mock",
            kind="mock",
            capabilities_json={"streaming": True, "provider": "pgvector-runtime-mock"},
        )
        session.add(provider)
        session.flush()
    model = AvailableModel(
        provider_id=provider.id,
        model_name="pgvector-runtime-mock-model",
        model_kind="chat",
        is_default=False,
        config_json={"reply_prefix": "MockEcho"},
    )
    session.add(model)
    session.flush()
    return model


def _ensure_character(session) -> Character:
    character = session.scalar(select(Character).where(Character.name == "Pgvector Runtime Character"))
    if character is not None:
        return character
    admin = session.scalar(select(User).where(User.username == "admin"))
    assert admin is not None
    character = Character(
        name="Pgvector Runtime Character",
        prompt_summary="Character used by pgvector runtime regression tests.",
        settings_json={},
        created_by_user_id=admin.id,
    )
    session.add(character)
    session.flush()
    return character


@pytest.fixture
def pgvector_runtime_client():
    database_url = _pgvector_database_url()
    if not database_url:
        pytest.skip("COCOON_PGVECTOR_TEST_DATABASE_URL is not configured")

    artifact_root = Path.cwd() / ".tmp_pytest" / f"pgvector-runtime-{uuid4().hex}"
    settings = Settings(
        environment="test",
        database_url=database_url,
        chat_dispatch_backend="memory",
        realtime_backend="memory",
        auto_create_schema=False,
        auto_seed_defaults=True,
        artifact_root=artifact_root,
        secret_key="test-secret-key-for-cocoon-sit-at-least-32-bytes",
        default_admin_username="admin",
        default_admin_email="admin@example.com",
        default_admin_password="admin",
    )

    bootstrap_container = AppContainer(settings)
    with bootstrap_container.engine.begin() as connection:
        connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        Base.metadata.drop_all(connection)
        Base.metadata.create_all(connection)
    bootstrap_container.shutdown()

    app = create_app(settings)
    with TestClient(app) as test_client:
        container = test_client.app.state.container
        with container.session_factory() as session:
            _ensure_mock_chat_model(session)
            session.commit()
        yield test_client

    cleanup_container = AppContainer(settings)
    with cleanup_container.engine.begin() as connection:
        Base.metadata.drop_all(connection)
    cleanup_container.shutdown()


@pytest.fixture
def pgvector_runtime_auth_headers(pgvector_runtime_client: TestClient) -> dict[str, str]:
    response = pgvector_runtime_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def pgvector_worker_runtime(pgvector_runtime_client: TestClient) -> WorkerRuntime:
    container = pgvector_runtime_client.app.state.container
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
        worker_name=container.settings.durable_job_worker_name,
    )


@pytest.mark.pgvector
def test_chat_group_flow_with_pgvector_memory_and_mock_ai(
    pgvector_runtime_client: TestClient,
    pgvector_worker_runtime: WorkerRuntime,
    pgvector_runtime_auth_headers: dict[str, str],
):
    client = pgvector_runtime_client
    auth_headers = pgvector_runtime_auth_headers
    container = client.app.state.container

    with container.session_factory() as session:
        model = _ensure_mock_chat_model(session)
        character = _ensure_character(session)
        container.embedding_provider_service.create_embedding_provider(
            session,
            EmbeddingProviderCreate(
                name="pgvector-runtime-local-cpu",
                kind="local_cpu",
                model_name="pgvector-runtime-local-cpu",
                config_json={"dimensions": 8, "device": "cpu"},
                is_enabled=True,
            ),
        )
        session.commit()
        model_id = model.id
        character_id = character.id

    room_response = client.post(
        "/api/v1/chat-groups",
        headers=auth_headers,
        json={
            "name": "Pgvector Runtime Group",
            "character_id": character_id,
            "selected_model_id": model_id,
        },
    )
    assert room_response.status_code == 200, room_response.text
    room = room_response.json()
    room_id = room["id"]

    with container.session_factory() as session:
        room_record = session.get(ChatGroupRoom, room_id)
        assert room_record is not None
        memory = MemoryChunk(
            chat_group_id=room_id,
            owner_user_id=room_record.owner_user_id,
            character_id=room_record.character_id,
            scope="dialogue",
            content="Prefers mountain tea and quiet evening chats",
            summary="Tea preference memory",
        )
        session.add(memory)
        session.flush()
        container.memory_service.index_memory_chunk(session, memory, source_text=memory.summary or memory.content)
        session.commit()

    access_token = auth_headers["Authorization"].split(" ", 1)[1]
    with client.websocket_connect(f"/api/v1/chat-groups/{room_id}/ws?access_token={access_token}") as websocket:
        send_response = client.post(
            f"/api/v1/chat-groups/{room_id}/messages",
            headers=auth_headers,
            json={
                "content": "Can you reply using the room memory?",
                "client_request_id": "pgvector-room-runtime-1",
                "timezone": "UTC",
            },
        )
        assert send_response.status_code == 202, send_response.text
        queued = websocket.receive_json()
        assert queued["type"] == "dispatch_queued"

        assert pgvector_worker_runtime.process_next_chat_dispatch() is True

        seen = []
        for _ in range(20):
            event = websocket.receive_json()
            seen.append(event)
            if event["type"] == "reply_done":
                break

    event_types = [item["type"] for item in seen]
    assert "reply_started" in event_types
    assert "reply_done" in event_types
    assert any(item["type"] == "reply_chunk" for item in seen)

    messages = client.get(f"/api/v1/chat-groups/{room_id}/messages", headers=auth_headers)
    assert messages.status_code == 200, messages.text
    payload = messages.json()
    assert any(item["role"] == "assistant" and item["content"].startswith("MockEcho:") for item in payload)
