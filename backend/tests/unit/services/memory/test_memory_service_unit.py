from types import SimpleNamespace

from app.models import EmbeddingProvider, MemoryChunk, MemoryEmbedding
from app.services.memory.service import MemoryRetrievalHit, MemoryService


def test_memory_retrieval_hit_to_artifact_payload_truncates_content():
    memory = MemoryChunk(id="memory-1", scope="dialogue", summary="summary", content="x" * 250)
    hit = MemoryRetrievalHit(
        memory=memory,
        similarity_score=0.75,
        matched_tags=["focus"],
        embedding_provider_id="embed-1",
    )

    payload = hit.to_artifact_payload()

    assert payload["memory_chunk_id"] == "memory-1"
    assert payload["content_preview"] == "x" * 200
    assert payload["matched_tags"] == ["focus"]


def test_memory_service_retrieve_visible_memories_without_vector_support():
    service = MemoryService()
    memories = [
        MemoryChunk(id="m1", scope="dialogue", content="one", tags_json=["focus"]),
        MemoryChunk(id="m2", scope="dialogue", content="two", tags_json=["other"]),
    ]
    service._load_candidate_memories = lambda *args, **kwargs: memories  # type: ignore[method-assign]
    service._supports_vector_search = lambda session: False  # type: ignore[method-assign]

    hits = service.retrieve_visible_memories(
        session=object(),
        active_tags=["focus"],
        cocoon_id="c1",
        query_text="hello",
        limit=2,
    )

    assert [item.memory.id for item in hits] == ["m1", "m2"]
    assert hits[0].matched_tags == ["focus"]
    assert hits[1].matched_tags == []
    assert all(item.similarity_score is None for item in hits)


def test_memory_service_retrieve_visible_memories_when_embedding_provider_missing():
    provider_registry = SimpleNamespace(resolve_embedding_provider=lambda session: None)
    service = MemoryService(provider_registry=provider_registry)
    memories = [MemoryChunk(id="m1", scope="dialogue", content="one", tags_json=["focus"])]
    service._load_candidate_memories = lambda *args, **kwargs: memories  # type: ignore[method-assign]
    service._supports_vector_search = lambda session: True  # type: ignore[method-assign]

    hits = service.retrieve_visible_memories(
        session=object(),
        active_tags=["focus"],
        cocoon_id="c1",
        query_text="hello",
        limit=1,
    )

    assert [item.memory.id for item in hits] == ["m1"]
    assert hits[0].embedding_provider_id is None


def test_memory_service_retrieve_visible_memories_with_vector_rows_and_backfill():
    rows = [
        ("m2", "embed-1", 0.2),
        ("m2", "embed-1", 0.2),
    ]
    session = SimpleNamespace(execute=lambda statement: SimpleNamespace(all=lambda: rows))
    provider = SimpleNamespace(
        embed_texts=lambda texts, model_name, provider_config: SimpleNamespace(vectors=[[0.1, 0.2]])
    )
    provider_record = SimpleNamespace(id="embed-1", model_name="embed-model")
    provider_registry = SimpleNamespace(
        resolve_embedding_provider=lambda current_session: (provider, provider_record, {"api_key": "secret"})
    )
    service = MemoryService(provider_registry=provider_registry)
    service._supports_vector_search = lambda current_session: True  # type: ignore[method-assign]
    service._load_candidate_memories = lambda *args, **kwargs: [  # type: ignore[method-assign]
        MemoryChunk(id="m1", scope="dialogue", content="one", tags_json=["focus"]),
        MemoryChunk(id="m2", scope="dialogue", content="two", tags_json=["focus", "other"]),
        MemoryChunk(id="m3", scope="dialogue", content="three", tags_json=[]),
    ]

    hits = service.retrieve_visible_memories(
        session=session,
        active_tags=["focus"],
        cocoon_id="c1",
        query_text="hello",
        limit=3,
    )

    assert [item.memory.id for item in hits] == ["m2", "m1", "m3"]
    assert hits[0].similarity_score == 0.8
    assert hits[0].embedding_provider_id == "embed-1"
    assert hits[1].similarity_score is None


def test_memory_service_retrieve_visible_memories_falls_back_when_embedding_fails():
    memories = [
        MemoryChunk(id="m1", scope="dialogue", content="one", tags_json=["focus"]),
        MemoryChunk(id="m2", scope="dialogue", content="two", tags_json=[]),
    ]
    provider = SimpleNamespace(embed_texts=lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("slow")))
    provider_record = SimpleNamespace(id="embed-1", model_name="embed-model")
    provider_registry = SimpleNamespace(
        resolve_embedding_provider=lambda current_session: (provider, provider_record, {"api_key": "secret"})
    )
    service = MemoryService(provider_registry=provider_registry)
    service._supports_vector_search = lambda current_session: True  # type: ignore[method-assign]
    service._load_candidate_memories = lambda *args, **kwargs: memories  # type: ignore[method-assign]

    hits = service.retrieve_visible_memories(
        session=object(),
        active_tags=["focus"],
        cocoon_id="c1",
        query_text="hello",
        limit=2,
    )

    assert [item.memory.id for item in hits] == ["m1", "m2"]
    assert all(item.similarity_score is None for item in hits)


def test_memory_service_index_memory_chunk_handles_disabled_and_missing_providers():
    memory_chunk = MemoryChunk(id="memory-1", scope="dialogue", content="hello")
    service = MemoryService(provider_registry=None)
    session = SimpleNamespace(get_bind=lambda: None)

    assert service.index_memory_chunk(session=session, memory_chunk=memory_chunk) is None

    service = MemoryService(provider_registry=SimpleNamespace(resolve_embedding_provider=lambda session: None))
    service._supports_vector_search = lambda session: True  # type: ignore[method-assign]
    assert service.index_memory_chunk(session=session, memory_chunk=memory_chunk) is None


def test_memory_service_index_memory_chunk_skips_vector_when_embedding_fails():
    provider = SimpleNamespace(embed_texts=lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("slow")))
    provider_record = EmbeddingProvider(id="embed-1", name="embed", model_name="embed-model", config_json={}, is_enabled=True)
    provider_registry = SimpleNamespace(
        resolve_embedding_provider=lambda session: (provider, provider_record, {"api_key": "secret"})
    )
    service = MemoryService(provider_registry=provider_registry)
    service._supports_vector_search = lambda session: True  # type: ignore[method-assign]
    memory_chunk = MemoryChunk(id="memory-1", scope="dialogue", content="hello", summary="summary")

    assert service.index_memory_chunk(session=object(), memory_chunk=memory_chunk) is None
    assert memory_chunk.embedding_ref is None


def test_memory_service_index_memory_chunk_creates_and_updates_embedding_records():
    provider = SimpleNamespace(
        embed_texts=lambda texts, model_name, provider_config: SimpleNamespace(
            vectors=[[0.5, 0.6]],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=0, total_tokens=1),
        )
    )
    provider_record = EmbeddingProvider(id="embed-1", name="embed", model_name="embed-model", config_json={}, is_enabled=True)
    provider_registry = SimpleNamespace(
        resolve_embedding_provider=lambda session: (provider, provider_record, {"api_key": "secret"})
    )
    service = MemoryService(provider_registry=provider_registry)
    service._supports_vector_search = lambda session: True  # type: ignore[method-assign]
    memory_chunk = MemoryChunk(id="memory-1", scope="dialogue", content="hello", summary="summary")

    class _FakeSession:
        def __init__(self):
            self.scalar_result = None
            self.added = []
            self.flush_count = 0

        def scalar(self, statement):
            return self.scalar_result

        def add(self, value):
            self.added.append(value)

        def flush(self):
            self.flush_count += 1

    create_session = _FakeSession()
    item = service.index_memory_chunk(
        session=create_session,
        memory_chunk=memory_chunk,
        source_text="source",
        meta_json={"origin": "test"},
    )

    assert isinstance(item, MemoryEmbedding)
    assert item.embedding == [0.5, 0.6]
    assert memory_chunk.embedding_ref == item.id
    assert create_session.added == [item]

    existing = MemoryEmbedding(
        memory_chunk_id="memory-1",
        embedding_provider_id="old",
        model_name="old-model",
        dimensions=1,
        embedding=[0.1],
        usage_json={},
        meta_json={},
    )
    update_session = _FakeSession()
    update_session.scalar_result = existing

    updated = service.index_memory_chunk(
        session=update_session,
        memory_chunk=memory_chunk,
        meta_json={"origin": "updated"},
    )

    assert updated is existing
    assert existing.embedding_provider_id == "embed-1"
    assert existing.model_name == "embed-model"
    assert existing.dimensions == 2
    assert existing.meta_json == {"origin": "updated"}


def test_memory_service_get_active_embedding_provider_returns_provider_record():
    provider_record = EmbeddingProvider(id="embed-1", name="embed", model_name="embed-model", config_json={}, is_enabled=True)
    provider_registry = SimpleNamespace(
        resolve_embedding_provider=lambda session: (SimpleNamespace(), provider_record, {"api_key": "secret"})
    )
    service = MemoryService(provider_registry=provider_registry)

    assert service.get_active_embedding_provider(object()) is provider_record
