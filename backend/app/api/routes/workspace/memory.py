from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_container, get_current_user, get_db, require_permission
from app.core.container import AppContainer
from app.models import MemoryChunk, MemoryEmbedding, MemoryTag
from app.models.entities import DurableJobType
from app.schemas.workspace.memory import (
    MemoryChunkOut,
    MemoryCompactionRequest,
    MemoryListOut,
    MemoryReorganizeRequest,
    MemoryUpdateRequest,
)
from app.schemas.workspace.jobs import DurableJobOut
from app.services.workspace.targets import list_cocoon_lineage_ids


router = APIRouter()

@router.get("/{cocoon_id}", response_model=MemoryListOut)
def list_memory(
    cocoon_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("memory:read")),
) -> MemoryListOut:
    cocoon = db.info["container"].authorization_service.require_cocoon_access(db, user, cocoon_id, write=False)
    memory_service = db.info["container"].memory_service
    memories = memory_service.list_target_memories(
        db,
        cocoon_id=cocoon_id,
        owner_user_id=cocoon.owner_user_id,
        include_inactive=True,
    )
    return MemoryListOut(
        items=[MemoryChunkOut.model_validate(memory_service.serialize_memory_chunk(db, item)) for item in memories],
        overview=memory_service.summarize_memories(db, memories),
    )


@router.post("/{cocoon_id}/compact", response_model=DurableJobOut)
def compact_memory(
    cocoon_id: str,
    payload: MemoryCompactionRequest,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
    _=Depends(require_permission("memory:write")),
):
    container.authorization_service.require_cocoon_access(db, user, cocoon_id, write=True)
    job = container.durable_jobs.enqueue(
        session=db,
        job_type=DurableJobType.compaction,
        lock_key=f"cocoon:{cocoon_id}:compaction",
        payload_json=payload.model_dump(),
        cocoon_id=cocoon_id,
    )
    return job


@router.patch("/{cocoon_id}/{memory_id}", response_model=MemoryChunkOut)
def update_memory(
    cocoon_id: str,
    memory_id: str,
    payload: MemoryUpdateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("memory:write")),
) -> MemoryChunk:
    cocoon = db.info["container"].authorization_service.require_cocoon_access(db, user, cocoon_id, write=True)
    memory = db.get(MemoryChunk, memory_id)
    cocoon_ids = set(list_cocoon_lineage_ids(db, cocoon_id) or [cocoon_id])
    allowed = memory and (
        memory.cocoon_id in cocoon_ids
        or (memory.owner_user_id == cocoon.owner_user_id and memory.memory_pool == "user_global")
    )
    if not allowed:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    updates = payload.model_dump(exclude_unset=True, exclude={"tags_json"})
    for field, value in updates.items():
        setattr(memory, field, value)
    if payload.tags_json is not None:
        memory.tags_json = db.info["container"].memory_service.resolve_or_create_memory_tags(
            db,
            owner_user_id=memory.owner_user_id or cocoon.owner_user_id,
            tag_refs=payload.tags_json,
        )
        db.query(MemoryTag).filter(MemoryTag.memory_chunk_id == memory.id).delete()
        for tag_id in memory.tags_json:
            db.add(MemoryTag(memory_chunk_id=memory.id, tag_id=tag_id))
    db.flush()
    db.info["container"].memory_service.index_memory_chunk(
        db,
        memory,
        source_text=memory.summary or memory.content,
        meta_json=memory.meta_json,
    )
    return MemoryChunkOut.model_validate(db.info["container"].memory_service.serialize_memory_chunk(db, memory))


@router.post("/{cocoon_id}/reorganize", response_model=DurableJobOut)
def reorganize_memory(
    cocoon_id: str,
    payload: MemoryReorganizeRequest,
    db: Session = Depends(get_db),
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
    _=Depends(require_permission("memory:write")),
):
    container.authorization_service.require_cocoon_access(db, user, cocoon_id, write=True)
    job = container.durable_jobs.enqueue(
        session=db,
        job_type=DurableJobType.memory_reorganize,
        lock_key=f"cocoon:{cocoon_id}:memory_reorganize",
        payload_json=payload.model_dump(),
        cocoon_id=cocoon_id,
    )
    return job


@router.delete("/{cocoon_id}/{memory_id}", response_model=MemoryChunkOut)
def delete_memory(
    cocoon_id: str,
    memory_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("memory:write")),
) -> MemoryChunk:
    cocoon = db.info["container"].authorization_service.require_cocoon_access(db, user, cocoon_id, write=True)
    memory = db.get(MemoryChunk, memory_id)
    cocoon_ids = set(list_cocoon_lineage_ids(db, cocoon_id) or [cocoon_id])
    if not memory or not (
        memory.cocoon_id in cocoon_ids
        or (memory.owner_user_id == cocoon.owner_user_id and memory.memory_pool == "user_global")
    ):
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    db.query(MemoryTag).filter(MemoryTag.memory_chunk_id == memory_id).delete()
    db.query(MemoryEmbedding).filter(MemoryEmbedding.memory_chunk_id == memory_id).delete()
    db.delete(memory)
    db.flush()
    return MemoryChunkOut.model_validate(db.info["container"].memory_service.serialize_memory_chunk(db, memory))
