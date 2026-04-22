import pytest
from app.models import MemoryChunk, MemoryTag
from app.services.memory.service import MemoryService

pytestmark = pytest.mark.integration


def test_memory_service_returns_recent_chunks_without_active_tags(client, default_cocoon_id):
    container = client.app.state.container
    service = MemoryService()
    with container.session_factory() as session:
        session.add_all(
            [
                MemoryChunk(cocoon_id=default_cocoon_id, scope="dialogue", content="First"),
                MemoryChunk(cocoon_id=default_cocoon_id, scope="dialogue", content="Second"),
                MemoryChunk(cocoon_id=default_cocoon_id, scope="dialogue", content="Third"),
            ]
        )
        session.commit()

    with container.session_factory() as session:
        memories = service.get_visible_memories(
            session=session,
            cocoon_id=default_cocoon_id,
            active_tags=[],
            limit=2,
        )
        assert len(memories) == 2


def test_memory_service_falls_back_to_memory_tag_links(client, default_cocoon_id):
    container = client.app.state.container
    service = MemoryService()
    with container.session_factory() as session:
        chunk = MemoryChunk(
            cocoon_id=default_cocoon_id,
            scope="dialogue",
            content="Needs fallback tag lookup",
            tags_json=["unrelated"],
        )
        session.add(chunk)
        session.flush()
        session.add(MemoryTag(memory_chunk_id=chunk.id, tag_id="focus"))
        session.commit()
        chunk_id = chunk.id

    with container.session_factory() as session:
        memories = service.get_visible_memories(
            session=session,
            cocoon_id=default_cocoon_id,
            active_tags=["focus"],
            limit=5,
        )
        assert [memory.id for memory in memories] == [chunk_id]
