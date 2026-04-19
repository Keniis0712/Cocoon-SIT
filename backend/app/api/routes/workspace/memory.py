from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_container, get_current_user, get_db, require_permission
from app.core.container import AppContainer
from app.models import MemoryChunk, MemoryEmbedding, MemoryTag
from app.models.entities import DurableJobType
from app.schemas.workspace.memory import MemoryChunkOut, MemoryCompactionRequest
from app.schemas.workspace.jobs import DurableJobOut


router = APIRouter()

@router.get("/{cocoon_id}", response_model=list[MemoryChunkOut])
def list_memory(
    cocoon_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("memory:read")),
) -> list[MemoryChunk]:
    db.info["container"].authorization_service.require_cocoon_access(db, user, cocoon_id, write=False)
    memories = list(
        db.scalars(
            select(MemoryChunk)
            .where(MemoryChunk.cocoon_id == cocoon_id)
            .order_by(MemoryChunk.created_at.desc())
        ).all()
    )
    return memories


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


@router.delete("/{cocoon_id}/{memory_id}", response_model=MemoryChunkOut)
def delete_memory(
    cocoon_id: str,
    memory_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("memory:write")),
) -> MemoryChunk:
    db.info["container"].authorization_service.require_cocoon_access(db, user, cocoon_id, write=True)
    memory = db.get(MemoryChunk, memory_id)
    if not memory or memory.cocoon_id != cocoon_id:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    db.query(MemoryTag).filter(MemoryTag.memory_chunk_id == memory_id).delete()
    db.query(MemoryEmbedding).filter(MemoryEmbedding.memory_chunk_id == memory_id).delete()
    db.delete(memory)
    db.flush()
    return memory
