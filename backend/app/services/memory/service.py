"""Memory retrieval and indexing service used by runtime context builders."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Float, bindparam, cast, select
from sqlalchemy.orm import Session

from app.models import EmbeddingProvider, MemoryChunk, MemoryEmbedding, MemoryTag
from app.models.vector import PGVector
from app.services.providers.registry import ProviderRegistry


@dataclass
class MemoryRetrievalHit:
    memory: MemoryChunk
    similarity_score: float | None
    matched_tags: list[str]
    embedding_provider_id: str | None

    def to_artifact_payload(self) -> dict:
        return {
            "memory_chunk_id": self.memory.id,
            "scope": self.memory.scope,
            "summary": self.memory.summary,
            "content_preview": self.memory.content[:200],
            "similarity_score": self.similarity_score,
            "matched_tags": self.matched_tags,
            "embedding_provider_id": self.embedding_provider_id,
        }


class MemoryService:
    """Loads visible memory chunks for a cocoon and indexes vector memories when supported."""

    def __init__(self, provider_registry: ProviderRegistry | None = None) -> None:
        self.provider_registry = provider_registry

    def _supports_vector_search(self, session: Session) -> bool:
        bind = session.get_bind()
        return bool(bind and bind.dialect.name == "postgresql" and self.provider_registry)

    def _load_candidate_memories(
        self,
        session: Session,
        active_tags: list[str],
        *,
        cocoon_id: str | None = None,
        owner_user_id: str | None = None,
        character_id: str | None = None,
        scopes: list[str] | None = None,
        limit: int,
    ) -> list[MemoryChunk]:
        query = select(MemoryChunk)
        if owner_user_id and character_id:
            query = query.where(
                MemoryChunk.owner_user_id == owner_user_id,
                MemoryChunk.character_id == character_id,
            )
        elif cocoon_id:
            query = query.where(MemoryChunk.cocoon_id == cocoon_id)
        if scopes:
            query = query.where(MemoryChunk.scope.in_(scopes))
        memories = list(
            session.scalars(
                query.order_by(MemoryChunk.created_at.desc()).limit(max(limit * 5, limit))
            ).all()
        )
        if not active_tags:
            return memories

        allowed_ids = {
            memory.id
            for memory in memories
            if not memory.tags_json or set(memory.tags_json).intersection(active_tags)
        }
        if not allowed_ids:
            tagged = session.scalars(
                select(MemoryTag).where(MemoryTag.tag_id.in_(active_tags))
            ).all()
            allowed_ids.update(item.memory_chunk_id for item in tagged)
        return [memory for memory in memories if memory.id in allowed_ids]

    def retrieve_visible_memories(
        self,
        session: Session,
        active_tags: list[str],
        *,
        cocoon_id: str | None = None,
        owner_user_id: str | None = None,
        character_id: str | None = None,
        query_text: str | None = None,
        scopes: list[str] | None = None,
        limit: int = 5,
    ) -> list[MemoryRetrievalHit]:
        candidates = self._load_candidate_memories(
            session,
            active_tags,
            cocoon_id=cocoon_id,
            owner_user_id=owner_user_id,
            character_id=character_id,
            scopes=scopes,
            limit=limit,
        )
        if not candidates:
            return []

        if not query_text or not self._supports_vector_search(session):
            return [
                MemoryRetrievalHit(
                    memory=memory,
                    similarity_score=None,
                    matched_tags=sorted(set(memory.tags_json).intersection(active_tags)),
                    embedding_provider_id=None,
                )
                for memory in candidates[:limit]
            ]

        resolved = self.provider_registry.resolve_embedding_provider(session)
        if resolved is None:
            return [
                MemoryRetrievalHit(
                    memory=memory,
                    similarity_score=None,
                    matched_tags=sorted(set(memory.tags_json).intersection(active_tags)),
                    embedding_provider_id=None,
                )
                for memory in candidates[:limit]
            ]
        provider, embedding_provider, runtime_config = resolved
        embedding_response = provider.embed_texts(
            [query_text],
            model_name=embedding_provider.model_name,
            provider_config=runtime_config,
        )
        if not embedding_response.vectors:
            return []

        query_vector = embedding_response.vectors[0]
        candidate_ids = [memory.id for memory in candidates]
        query_vector_type = PGVector(len(query_vector))
        query_vector_param = bindparam(
            "query_vector",
            value=query_vector,
            type_=query_vector_type,
        )
        distance_expr = cast(
            MemoryEmbedding.embedding.cosine_distance(cast(query_vector_param, query_vector_type)),
            Float,
        ).label("distance")
        rows = session.execute(
            select(
                MemoryEmbedding.memory_chunk_id,
                MemoryEmbedding.embedding_provider_id,
                distance_expr,
            )
            .where(MemoryEmbedding.memory_chunk_id.in_(candidate_ids))
            .order_by(distance_expr.asc())
            .limit(limit * 3)
        ).all()

        by_id = {memory.id: memory for memory in candidates}
        hits: list[MemoryRetrievalHit] = []
        seen_ids: set[str] = set()
        for memory_chunk_id, embedding_provider_id, distance in rows:
            memory = by_id.get(memory_chunk_id)
            if not memory or memory_chunk_id in seen_ids:
                continue
            similarity = None if distance is None else max(0.0, 1.0 - float(distance))
            hits.append(
                MemoryRetrievalHit(
                    memory=memory,
                    similarity_score=similarity,
                    matched_tags=sorted(set(memory.tags_json).intersection(active_tags)),
                    embedding_provider_id=embedding_provider_id,
                )
            )
            seen_ids.add(memory_chunk_id)

        if len(hits) < limit:
            for memory in candidates:
                if memory.id in seen_ids:
                    continue
                hits.append(
                    MemoryRetrievalHit(
                        memory=memory,
                        similarity_score=None,
                        matched_tags=sorted(set(memory.tags_json).intersection(active_tags)),
                        embedding_provider_id=None,
                    )
                )
                if len(hits) >= limit:
                    break
        return hits[:limit]

    def get_visible_memories(
        self,
        session: Session,
        active_tags: list[str],
        limit: int = 5,
        *,
        cocoon_id: str | None = None,
        owner_user_id: str | None = None,
        character_id: str | None = None,
        query_text: str | None = None,
        scopes: list[str] | None = None,
    ) -> list[MemoryChunk]:
        return [
            hit.memory
            for hit in self.retrieve_visible_memories(
                session,
                active_tags,
                cocoon_id=cocoon_id,
                owner_user_id=owner_user_id,
                character_id=character_id,
                query_text=query_text,
                scopes=scopes,
                limit=limit,
            )
        ]

    def index_memory_chunk(
        self,
        session: Session,
        memory_chunk: MemoryChunk,
        *,
        source_text: str | None = None,
        meta_json: dict | None = None,
    ) -> MemoryEmbedding | None:
        if not self._supports_vector_search(session):
            return None
        resolved = self.provider_registry.resolve_embedding_provider(session)
        if resolved is None:
            return None
        provider, embedding_provider, runtime_config = resolved
        response = provider.embed_texts(
            [source_text or memory_chunk.summary or memory_chunk.content],
            model_name=embedding_provider.model_name,
            provider_config=runtime_config,
        )
        if not response.vectors:
            return None

        item = session.scalar(
            select(MemoryEmbedding).where(MemoryEmbedding.memory_chunk_id == memory_chunk.id)
        )
        if item is None:
            item = MemoryEmbedding(
                memory_chunk_id=memory_chunk.id,
                embedding_provider_id=embedding_provider.id,
                model_name=embedding_provider.model_name,
                dimensions=len(response.vectors[0]),
                embedding=response.vectors[0],
                usage_json={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                meta_json=meta_json or {},
            )
            session.add(item)
            session.flush()
        else:
            item.embedding_provider_id = embedding_provider.id
            item.model_name = embedding_provider.model_name
            item.dimensions = len(response.vectors[0])
            item.embedding = response.vectors[0]
            item.usage_json = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            item.meta_json = meta_json or {}
            session.flush()
        memory_chunk.embedding_ref = item.id
        session.flush()
        return item

    def get_active_embedding_provider(self, session: Session) -> EmbeddingProvider | None:
        resolved = self.provider_registry.resolve_embedding_provider(session) if self.provider_registry else None
        if resolved is None:
            return None
        _, provider_record, _ = resolved
        return provider_record
