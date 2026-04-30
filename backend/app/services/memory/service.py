"""Memory retrieval and indexing service used by runtime context builders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
import math
from typing import Any

from sqlalchemy import Float, and_, bindparam, cast, delete, or_, select
from sqlalchemy.orm import Session

from app.models import (
    EmbeddingProvider,
    FactCacheEntry,
    MemoryCandidate,
    MemoryChunk,
    MemoryEmbedding,
    MemoryTag,
    TagRegistry,
)
from app.models.identity import new_id
from app.models.vector import PGVector
from app.services.catalog.tag_policy import is_tag_visible_in_target
from app.services.providers.registry import ProviderRegistry
from app.services.workspace.targets import list_cocoon_lineage_ids


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class MemoryRetrievalHit:
    memory: MemoryChunk
    similarity_score: float | None
    matched_tags: list[str]
    embedding_provider_id: str | None
    final_score: float | None = None
    score_breakdown: dict[str, float] | None = None

    def to_artifact_payload(self) -> dict:
        return {
            "memory_chunk_id": self.memory.id,
            "memory_pool": self.memory.memory_pool,
            "memory_type": self.memory.memory_type,
            "scope": self.memory.scope,
            "summary": self.memory.summary,
            "content_preview": self.memory.content[:200],
            "similarity_score": self.similarity_score,
            "final_score": self.final_score,
            "score_breakdown": self.score_breakdown or {},
            "importance": self.memory.importance,
            "confidence": self.memory.confidence,
            "status": self.memory.status,
            "matched_tags": self.matched_tags,
            "embedding_provider_id": self.embedding_provider_id,
        }


class MemoryService:
    """Loads visible memories, fact cache, and memory candidates for runtime use."""

    logger = logging.getLogger(__name__)

    def __init__(self, provider_registry: ProviderRegistry | None = None) -> None:
        self.provider_registry = provider_registry

    def _supports_vector_search(self, session: Session) -> bool:
        bind = session.get_bind()
        return bool(bind and bind.dialect.name == "postgresql" and self.provider_registry)

    def _tag_filtered(
        self,
        session: Session,
        memories: list[MemoryChunk],
        active_tags: list[str],
        *,
        chat_group_id: str | None = None,
    ) -> list[MemoryChunk]:
        if chat_group_id:
            tags = {tag.id: tag for tag in session.scalars(select(TagRegistry)).all()}
            memories = [
                memory
                for memory in memories
                if all(
                    (
                        tag_id not in tags
                        or is_tag_visible_in_target(
                            session,
                            tags[tag_id],
                            target_type="chat_group",
                            target_id=chat_group_id,
                        )
                    )
                    for tag_id in (memory.tags_json or [])
                )
            ]
        if not active_tags:
            return memories
        return [
            memory
            for memory in memories
            if not memory.tags_json or set(memory.tags_json).intersection(active_tags)
        ]

    def _build_visibility_filter(
        self,
        session: Session,
        *,
        cocoon_id: str | None,
        chat_group_id: str | None,
        owner_user_id: str | None,
    ):
        if cocoon_id:
            lineage_ids = list_cocoon_lineage_ids(session, cocoon_id) or [cocoon_id]
            filters = [
                and_(
                    MemoryChunk.memory_pool == "tree_private",
                    MemoryChunk.cocoon_id.in_(lineage_ids),
                )
            ]
            if owner_user_id:
                filters.append(
                    and_(
                        MemoryChunk.memory_pool == "user_global",
                        MemoryChunk.owner_user_id == owner_user_id,
                    )
                )
            return or_(*filters)
        if chat_group_id:
            filters = [
                and_(
                    MemoryChunk.memory_pool == "room_local",
                    MemoryChunk.chat_group_id == chat_group_id,
                )
            ]
            if owner_user_id:
                filters.append(
                    and_(
                        MemoryChunk.memory_pool == "user_global",
                        MemoryChunk.owner_user_id == owner_user_id,
                    )
                )
            return or_(*filters)
        return MemoryChunk.id.is_(None)

    def list_fact_cache_entries(
        self,
        session: Session,
        *,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
        limit: int = 10,
    ) -> list[FactCacheEntry]:
        now = utcnow()
        query = select(FactCacheEntry).where(
            or_(
                FactCacheEntry.valid_until.is_(None),
                FactCacheEntry.valid_until >= now,
            )
        )
        if cocoon_id:
            query = query.where(FactCacheEntry.cocoon_id == cocoon_id)
        elif chat_group_id:
            query = query.where(FactCacheEntry.chat_group_id == chat_group_id)
        else:
            return []
        return list(
            session.scalars(query.order_by(FactCacheEntry.updated_at.desc()).limit(limit)).all()
        )

    def upsert_fact_cache_entry(
        self,
        session: Session,
        *,
        cache_key: str,
        content: str,
        summary: str | None = None,
        valid_until: datetime | None = None,
        meta_json: dict[str, Any] | None = None,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
    ) -> FactCacheEntry:
        query = select(FactCacheEntry).where(FactCacheEntry.cache_key == cache_key)
        if cocoon_id:
            query = query.where(FactCacheEntry.cocoon_id == cocoon_id)
        elif chat_group_id:
            query = query.where(FactCacheEntry.chat_group_id == chat_group_id)
        item = session.scalar(query)
        if item is None:
            item = FactCacheEntry(
                id=new_id(),
                cocoon_id=cocoon_id,
                chat_group_id=chat_group_id,
                cache_key=cache_key,
                content=content,
                summary=summary,
                valid_until=valid_until,
                meta_json=meta_json or {},
            )
            session.add(item)
        else:
            item.content = content
            item.summary = summary
            item.valid_until = valid_until
            item.meta_json = meta_json or {}
        item.last_accessed_at = utcnow()
        session.flush()
        return item

    def delete_fact_cache_entry(
        self,
        session: Session,
        *,
        cache_key: str,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
    ) -> None:
        query = delete(FactCacheEntry).where(FactCacheEntry.cache_key == cache_key)
        if cocoon_id:
            query = query.where(FactCacheEntry.cocoon_id == cocoon_id)
        elif chat_group_id:
            query = query.where(FactCacheEntry.chat_group_id == chat_group_id)
        session.execute(query)
        session.flush()

    def _load_candidate_memories(
        self,
        session: Session,
        active_tags: list[str],
        *,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
        owner_user_id: str | None = None,
        scopes: list[str] | None = None,
        limit: int,
    ) -> list[MemoryChunk]:
        query = select(MemoryChunk).where(MemoryChunk.status == "active")
        query = query.where(
            or_(
                MemoryChunk.valid_until.is_(None),
                MemoryChunk.valid_until >= utcnow(),
            )
        )
        query = query.where(
            self._build_visibility_filter(
                session,
                cocoon_id=cocoon_id,
                chat_group_id=chat_group_id,
                owner_user_id=owner_user_id,
            )
        )
        if scopes:
            query = query.where(MemoryChunk.scope.in_(scopes))
        memories = list(
            session.scalars(
                query.order_by(MemoryChunk.updated_at.desc()).limit(max(limit * 6, limit))
            ).all()
        )
        return self._tag_filtered(
            session,
            memories,
            active_tags,
            chat_group_id=chat_group_id,
        )

    def _recency_score(self, memory: MemoryChunk) -> float:
        timestamp = memory.last_accessed_at or memory.updated_at or memory.created_at
        age_days = max(0.0, (utcnow() - timestamp).total_seconds() / 86400.0)
        return 1.0 / (1.0 + age_days / 30.0)

    def _score_hit(
        self,
        hit: MemoryRetrievalHit,
        *,
        active_tags: list[str],
        weights: dict[str, float],
    ) -> MemoryRetrievalHit:
        vector_score = float(hit.similarity_score or 0.0)
        importance_score = max(0.0, min(float(hit.memory.importance or 0) / 5.0, 1.0))
        recency_score = self._recency_score(hit.memory)
        confidence_score = max(0.0, min(float(hit.memory.confidence or 0) / 5.0, 1.0))
        tag_match_score = 0.0
        if active_tags:
            tag_match_score = min(len(hit.matched_tags) / max(len(active_tags), 1), 1.0)
        breakdown = {
            "vector": vector_score,
            "importance": importance_score,
            "recency": recency_score,
            "confidence": confidence_score,
            "tag_match": tag_match_score,
        }
        hit.score_breakdown = breakdown
        hit.final_score = sum(
            breakdown[key] * float(weights.get(f"{key}_weight", 0.0))
            for key in breakdown
        )
        return hit

    def retrieve_visible_memories(
        self,
        session: Session,
        active_tags: list[str],
        *,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
        owner_user_id: str | None = None,
        character_id: str | None = None,
        query_text: str | None = None,
        scopes: list[str] | None = None,
        limit: int = 5,
        profile: dict[str, Any] | None = None,
    ) -> list[MemoryRetrievalHit]:
        resolved_profile = profile or {}
        limit = int(resolved_profile.get("prompt_memory_limit") or limit or 5)
        candidates = self._load_candidate_memories(
            session,
            active_tags,
            cocoon_id=cocoon_id,
            chat_group_id=chat_group_id,
            owner_user_id=owner_user_id,
            scopes=scopes,
            limit=int(resolved_profile.get("vector_recall_limit") or limit),
        )
        if not candidates:
            return []

        base_hits: list[MemoryRetrievalHit] = [
            MemoryRetrievalHit(
                memory=memory,
                similarity_score=None,
                matched_tags=sorted(set(memory.tags_json or []).intersection(active_tags)),
                embedding_provider_id=None,
            )
            for memory in candidates
        ]
        if not query_text or not self._supports_vector_search(session):
            scored = [self._score_hit(hit, active_tags=active_tags, weights=resolved_profile) for hit in base_hits]
            scored.sort(key=lambda item: (item.final_score or 0.0, item.memory.updated_at), reverse=True)
            return scored[:limit]

        resolved = self.provider_registry.resolve_embedding_provider(session)
        if resolved is None:
            scored = [self._score_hit(hit, active_tags=active_tags, weights=resolved_profile) for hit in base_hits]
            scored.sort(key=lambda item: (item.final_score or 0.0, item.memory.updated_at), reverse=True)
            return scored[:limit]
        provider, embedding_provider, runtime_config = resolved
        try:
            embedding_response = provider.embed_texts(
                [query_text],
                model_name=embedding_provider.model_name,
                provider_config=runtime_config,
            )
        except Exception:
            self.logger.warning(
                "Memory vector retrieval embedding failed; falling back to local ranking",
                exc_info=True,
            )
            scored = [self._score_hit(hit, active_tags=active_tags, weights=resolved_profile) for hit in base_hits]
            scored.sort(key=lambda item: (item.final_score or 0.0, item.memory.updated_at), reverse=True)
            return scored[:limit]
        if not embedding_response.vectors:
            return []

        query_vector = embedding_response.vectors[0]
        candidate_ids = [memory.id for memory in candidates]
        query_vector_type = PGVector(len(query_vector))
        query_vector_param = bindparam("query_vector", value=query_vector, type_=query_vector_type)
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
            .limit(max(limit * 4, limit))
        ).all()

        by_id = {memory.id: memory for memory in candidates}
        hits: list[MemoryRetrievalHit] = []
        seen_ids: set[str] = set()
        for memory_chunk_id, embedding_provider_id, distance in rows:
            memory = by_id.get(memory_chunk_id)
            if not memory or memory_chunk_id in seen_ids:
                continue
            similarity = None if distance is None else max(0.0, 1.0 - float(distance))
            hit = MemoryRetrievalHit(
                memory=memory,
                similarity_score=similarity,
                matched_tags=sorted(set(memory.tags_json or []).intersection(active_tags)),
                embedding_provider_id=embedding_provider_id,
            )
            hits.append(self._score_hit(hit, active_tags=active_tags, weights=resolved_profile))
            seen_ids.add(memory_chunk_id)

        for memory in candidates:
            if memory.id in seen_ids:
                continue
            hits.append(
                self._score_hit(
                    MemoryRetrievalHit(
                        memory=memory,
                        similarity_score=None,
                        matched_tags=sorted(set(memory.tags_json or []).intersection(active_tags)),
                        embedding_provider_id=None,
                    ),
                    active_tags=active_tags,
                    weights=resolved_profile,
                )
            )
        hits.sort(
            key=lambda item: (
                item.final_score if item.final_score is not None else -math.inf,
                item.memory.updated_at,
            ),
            reverse=True,
        )
        return hits[:limit]

    def get_visible_memories(
        self,
        session: Session,
        active_tags: list[str],
        limit: int = 5,
        *,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
        owner_user_id: str | None = None,
        character_id: str | None = None,
        query_text: str | None = None,
        scopes: list[str] | None = None,
        profile: dict[str, Any] | None = None,
    ) -> list[MemoryChunk]:
        return [
            hit.memory
            for hit in self.retrieve_visible_memories(
                session,
                active_tags,
                cocoon_id=cocoon_id,
                chat_group_id=chat_group_id,
                owner_user_id=owner_user_id,
                character_id=character_id,
                query_text=query_text,
                scopes=scopes,
                limit=limit,
                profile=profile,
            )
        ]

    def touch_memories(
        self,
        session: Session,
        memory_ids: list[str],
        *,
        importance_boost: float = 0.0,
    ) -> None:
        if not memory_ids:
            return
        now = utcnow()
        for memory in session.scalars(select(MemoryChunk).where(MemoryChunk.id.in_(memory_ids))).all():
            memory.last_accessed_at = now
            memory.access_count = int(memory.access_count or 0) + 1
            if importance_boost:
                memory.importance = max(0, min(5, int(round((memory.importance or 0) + importance_boost))))
        session.flush()

    def upsert_candidate(
        self,
        session: Session,
        *,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
        owner_user_id: str | None = None,
        character_id: str | None = None,
        memory_pool: str = "tree_private",
        memory_type: str = "preference",
        summary: str | None = None,
        content: str,
        tags_json: list[str] | None = None,
        importance: int = 2,
        confidence: int = 2,
        ttl_hours: int = 72,
        meta_json: dict[str, Any] | None = None,
    ) -> MemoryCandidate:
        now = utcnow()
        query = select(MemoryCandidate).where(
            MemoryCandidate.content == content,
            MemoryCandidate.memory_pool == memory_pool,
        )
        if cocoon_id:
            query = query.where(MemoryCandidate.cocoon_id == cocoon_id)
        elif chat_group_id:
            query = query.where(MemoryCandidate.chat_group_id == chat_group_id)
        item = session.scalar(query.limit(1))
        if item is None:
            item = MemoryCandidate(
                cocoon_id=cocoon_id,
                chat_group_id=chat_group_id,
                owner_user_id=owner_user_id,
                character_id=character_id,
                memory_pool=memory_pool,
                memory_type=memory_type,
                summary=summary,
                content=content,
                tags_json=tags_json or [],
                importance=importance,
                confidence=confidence,
                hit_count=1,
                first_seen_at=now,
                last_seen_at=now,
                valid_until=now + timedelta(hours=max(ttl_hours, 1)),
                meta_json=meta_json or {},
            )
            session.add(item)
        else:
            item.summary = summary
            item.tags_json = tags_json or item.tags_json
            item.importance = importance
            item.confidence = confidence
            item.hit_count = int(item.hit_count or 0) + 1
            item.last_seen_at = now
            item.valid_until = now + timedelta(hours=max(ttl_hours, 1))
            item.meta_json = meta_json or item.meta_json
        session.flush()
        return item

    def promote_candidate_to_memory(
        self,
        session: Session,
        candidate: MemoryCandidate,
        *,
        source_kind: str = "candidate_promotion",
    ) -> MemoryChunk:
        memory = MemoryChunk(
            cocoon_id=candidate.cocoon_id,
            chat_group_id=candidate.chat_group_id,
            owner_user_id=candidate.owner_user_id,
            character_id=candidate.character_id,
            memory_pool=candidate.memory_pool,
            memory_type=candidate.memory_type,
            scope="candidate",
            content=candidate.content,
            summary=candidate.summary,
            tags_json=list(candidate.tags_json or []),
            importance=max(3, int(candidate.importance or 3)),
            confidence=max(1, int(candidate.confidence or 3)),
            status="active",
            valid_until=None,
            last_accessed_at=None,
            access_count=0,
            source_kind=source_kind,
            meta_json=dict(candidate.meta_json or {}),
        )
        session.add(memory)
        session.flush()
        for tag_id in memory.tags_json:
            session.add(MemoryTag(memory_chunk_id=memory.id, tag_id=tag_id))
        self.index_memory_chunk(
            session,
            memory,
            source_text=memory.summary or memory.content,
            meta_json=memory.meta_json,
        )
        session.delete(candidate)
        session.flush()
        return memory

    def summarize_memories(
        self,
        items: list[MemoryChunk],
    ) -> dict[str, Any]:
        if not items:
            return {
                "total": 0,
                "by_pool": {},
                "by_type": {},
                "by_status": {},
                "tag_cloud": [],
                "importance_average": 0,
                "confidence_average": 0,
            }
        by_pool: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        tag_counts: dict[str, int] = {}
        importance_total = 0
        confidence_total = 0
        for item in items:
            by_pool[item.memory_pool] = by_pool.get(item.memory_pool, 0) + 1
            by_type[item.memory_type] = by_type.get(item.memory_type, 0) + 1
            by_status[item.status] = by_status.get(item.status, 0) + 1
            importance_total += int(item.importance or 0)
            confidence_total += int(item.confidence or 0)
            for tag in item.tags_json or []:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        tag_cloud = [
            {"tag": tag, "count": count}
            for tag, count in sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:24]
        ]
        return {
            "total": len(items),
            "by_pool": by_pool,
            "by_type": by_type,
            "by_status": by_status,
            "tag_cloud": tag_cloud,
            "importance_average": round(importance_total / len(items), 2),
            "confidence_average": round(confidence_total / len(items), 2),
        }

    def list_target_memories(
        self,
        session: Session,
        *,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
        owner_user_id: str | None = None,
        include_inactive: bool = True,
    ) -> list[MemoryChunk]:
        query = select(MemoryChunk).where(
            self._build_visibility_filter(
                session,
                cocoon_id=cocoon_id,
                chat_group_id=chat_group_id,
                owner_user_id=owner_user_id,
            )
        )
        if not include_inactive:
            query = query.where(MemoryChunk.status == "active")
        return list(
            session.scalars(
                query.order_by(MemoryChunk.updated_at.desc(), MemoryChunk.created_at.desc())
            ).all()
        )

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
        try:
            response = provider.embed_texts(
                [source_text or memory_chunk.summary or memory_chunk.content],
                model_name=embedding_provider.model_name,
                provider_config=runtime_config,
            )
        except Exception:
            self.logger.warning(
                "Memory chunk embedding failed; skipping vector index memory_chunk_id=%s",
                memory_chunk.id,
                exc_info=True,
            )
            return None
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
