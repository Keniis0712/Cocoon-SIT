import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.container import AppContainer
from app.models import (
    Base,
    AvailableModel,
    Character,
    Cocoon,
    EmbeddingProvider,
    MemoryChunk,
    ModelProvider,
    SessionState,
    User,
)
from app.schemas.catalog.embedding_providers import EmbeddingProviderCreate, EmbeddingProviderUpdate


def _pgvector_database_url() -> str | None:
    return os.getenv("COCOON_PGVECTOR_TEST_DATABASE_URL")


def _enable_local_embedding_provider(container: AppContainer, session) -> tuple[EmbeddingProvider, EmbeddingProvider]:
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
    return first, second


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
        if model is None:
            provider = session.scalar(select(ModelProvider).where(ModelProvider.name == "pgvector-test-mock"))
            if provider is None:
                provider = ModelProvider(
                    name="pgvector-test-mock",
                    kind="mock",
                    capabilities_json={"streaming": True, "provider": "pgvector-test-mock"},
                )
                session.add(provider)
                session.flush()
            model = AvailableModel(
                provider_id=provider.id,
                model_name="pgvector-test-model",
                model_kind="chat",
                is_default=True,
                config_json={"reply_prefix": "Echo"},
            )
            session.add(model)
            session.flush()
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
        first, second = _enable_local_embedding_provider(container, session)
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
            active_tags=[],
            cocoon_id=cocoon_id,
            query_text="apple dessert preference",
            limit=2,
        )
        assert hits
        assert any(hit.memory.summary == "Apple pie preferences" for hit in hits)
        assert any(hit.similarity_score is not None for hit in hits)

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
            active_tags=[],
            cocoon_id=cocoon_id,
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
                active_tags=[],
                cocoon_id=cocoon_id,
                query_text="apple dessert preference",
                limit=2,
            )


@pytest.mark.pgvector
def test_pgvector_memory_retrieval_supports_user_character_scope(pgvector_container):
    container, cocoon_id = pgvector_container

    with container.session_factory() as session:
        _enable_local_embedding_provider(container, session)
        cocoon = session.get(Cocoon, cocoon_id)
        assert cocoon is not None
        scoped_memory = MemoryChunk(
            cocoon_id=cocoon.id,
            owner_user_id=cocoon.owner_user_id,
            character_id=cocoon.character_id,
            scope="dialogue",
            content="Tea ceremony preferences and oolong tasting notes",
            summary="Tea ceremony preferences",
        )
        unscoped_memory = MemoryChunk(
            cocoon_id=cocoon.id,
            scope="dialogue",
            content="Deployment checklist and incident timeline",
            summary="Deployment checklist",
        )
        session.add_all([scoped_memory, unscoped_memory])
        session.flush()
        container.memory_service.index_memory_chunk(
            session,
            scoped_memory,
            source_text=scoped_memory.summary or scoped_memory.content,
        )
        container.memory_service.index_memory_chunk(
            session,
            unscoped_memory,
            source_text=unscoped_memory.summary or unscoped_memory.content,
        )
        session.commit()

    with container.session_factory() as session:
        cocoon = session.get(Cocoon, cocoon_id)
        assert cocoon is not None
        hits = container.memory_service.retrieve_visible_memories(
            session,
            active_tags=[],
            owner_user_id=cocoon.owner_user_id,
            character_id=cocoon.character_id,
            query_text="tea tasting preference",
            limit=2,
        )
        assert hits
        assert hits[0].memory.summary == "Tea ceremony preferences"
        assert hits[0].similarity_score is not None
