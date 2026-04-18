import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.container import AppContainer
from app.models import Base, AvailableModel, Character, Cocoon, EmbeddingProvider, MemoryChunk, SessionState, User
from app.schemas.catalog.embedding_providers import EmbeddingProviderCreate, EmbeddingProviderUpdate


def _pgvector_database_url() -> str | None:
    return os.getenv("COCOON_PGVECTOR_TEST_DATABASE_URL")


@pytest.fixture
def pgvector_container():
    database_url = _pgvector_database_url()
    if not database_url:
        pytest.skip("COCOON_PGVECTOR_TEST_DATABASE_URL is not configured")

    artifact_root = Path.cwd() / ".tmp_pytest" / f"pgvector-{uuid4().hex}"
    settings = Settings(
        environment="test",
        database_url=database_url,
        chat_dispatch_backend="memory",
        realtime_backend="memory",
        auto_create_schema=False,
        auto_seed_defaults=False,
        artifact_root=artifact_root,
        default_admin_username="admin",
        default_admin_email="admin@example.com",
        default_admin_password="admin",
    )
    container = AppContainer(settings)
    with container.engine.begin() as connection:
        connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        Base.metadata.drop_all(connection)
        Base.metadata.create_all(connection)
    with container.session_factory() as session:
        container.bootstrap_service.seed_default_data(session)
        admin = session.scalar(select(User).where(User.username == settings.default_admin_username))
        model = session.scalar(select(AvailableModel).order_by(AvailableModel.created_at.asc()))
        assert admin is not None
        assert model is not None
        character = Character(
            name="Vector Test Character",
            prompt_summary="Vector test",
            settings_json={},
            created_by_user_id=admin.id,
        )
        session.add(character)
        session.flush()
        cocoon = Cocoon(
            name="Vector Cocoon",
            owner_user_id=admin.id,
            character_id=character.id,
            selected_model_id=model.id,
        )
        session.add(cocoon)
        session.flush()
        session.add(SessionState(cocoon_id=cocoon.id, persona_json={}, active_tags_json=[]))
        session.commit()
        cocoon_id = cocoon.id
    try:
        yield container, cocoon_id
    finally:
        with container.engine.begin() as connection:
            Base.metadata.drop_all(connection)
        container.shutdown()


@pytest.mark.pgvector
def test_pgvector_memory_retrieval_and_single_active_provider(pgvector_container):
    container, cocoon_id = pgvector_container

    with container.session_factory() as session:
        first = container.embedding_provider_service.create_embedding_provider(
            session,
            EmbeddingProviderCreate(
                name="local-cpu-a",
                kind="local_cpu",
                model_name="local-a",
                config_json={"dimensions": 8, "device": "cpu"},
                is_enabled=True,
            ),
        )
        second = container.embedding_provider_service.create_embedding_provider(
            session,
            EmbeddingProviderCreate(
                name="local-cpu-b",
                kind="local_cpu",
                model_name="local-b",
                config_json={"dimensions": 8, "device": "cpu"},
                is_enabled=True,
            ),
        )
        session.commit()
        session.refresh(first)
        session.refresh(second)
        assert first.is_enabled is False
        assert second.is_enabled is True

    with container.session_factory() as session:
        apple = MemoryChunk(
            cocoon_id=cocoon_id,
            scope="dialogue",
            content="Apple pie preferences and orchard notes",
            summary="Apple pie preferences",
        )
        server = MemoryChunk(
            cocoon_id=cocoon_id,
            scope="dialogue",
            content="Server error budget and oncall rotation",
            summary="Server error budget",
        )
        session.add_all([apple, server])
        session.flush()
        container.memory_service.index_memory_chunk(session, apple, source_text=apple.summary or apple.content)
        container.memory_service.index_memory_chunk(session, server, source_text=server.summary or server.content)
        session.commit()

    with container.session_factory() as session:
        hits = container.memory_service.retrieve_visible_memories(
            session,
            cocoon_id,
            active_tags=[],
            query_text="apple dessert preference",
            limit=2,
        )
        assert hits
        assert hits[0].memory.summary == "Apple pie preferences"
        assert hits[0].similarity_score is not None

        active_provider = session.scalar(
            select(EmbeddingProvider).where(EmbeddingProvider.is_enabled.is_(True))
        )
        assert active_provider is not None
        container.embedding_provider_service.update_embedding_provider(
            session,
            active_provider.id,
            EmbeddingProviderUpdate(is_enabled=False),
        )
        session.commit()

    with container.session_factory() as session:
        hits = container.memory_service.retrieve_visible_memories(
            session,
            cocoon_id,
            active_tags=[],
            query_text="apple dessert preference",
            limit=2,
        )
        assert hits
        assert all(hit.similarity_score is None for hit in hits)

        providers = list(session.scalars(select(EmbeddingProvider).order_by(EmbeddingProvider.created_at.asc())).all())
        assert len(providers) == 2
        providers[0].is_enabled = True
        providers[1].is_enabled = True
        session.commit()

    with container.session_factory() as session:
        with pytest.raises(ValueError):
            container.memory_service.retrieve_visible_memories(
                session,
                cocoon_id,
                active_tags=[],
                query_text="apple dessert preference",
                limit=2,
            )
