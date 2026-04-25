from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.api.wakeup_serialization import serialize_wakeup_task
from app.models import (
    ActionDispatch,
    AuditArtifact,
    AuditLink,
    AuditRun,
    AuditStep,
    Checkpoint,
    Cocoon,
    CocoonMergeJob,
    CocoonPullJob,
    CocoonTagBinding,
    DurableJob,
    FailedRound,
    MemoryChunk,
    MemoryEmbedding,
    MemoryTag,
    Message,
    MessageTag,
    PluginDispatchRecord,
    PluginImDeliveryOutbox,
    SessionState,
    User,
    WakeupTask,
)
from app.schemas.observability.wakeups import WakeupTaskOut
from app.schemas.workspace.cocoons import (
    CocoonCreate,
    CocoonOut,
    CocoonTreeNode,
    CocoonUpdate,
    SessionStateOut,
)
from app.services.runtime.scheduling.wakeup_tasks import list_wakeup_tasks
from app.services.workspace.targets import ensure_session_state, get_session_state as load_session_state


router = APIRouter()


def _collect_cocoon_subtree_ids(db: Session, root_id: str) -> list[str]:
    cocoons = list(db.scalars(select(Cocoon)).all())
    children_by_parent: dict[str | None, list[str]] = {}
    for item in cocoons:
        children_by_parent.setdefault(item.parent_id, []).append(item.id)
    ordered: list[str] = []
    queue = [root_id]
    while queue:
        current = queue.pop(0)
        ordered.append(current)
        queue.extend(children_by_parent.get(current, []))
    return ordered


def _delete_cocoon_subtree(db: Session, cocoon_ids: list[str]) -> None:
    if not cocoon_ids:
        return
    action_ids = list(
        db.scalars(select(ActionDispatch.id).where(ActionDispatch.cocoon_id.in_(cocoon_ids))).all()
    )
    audit_run_ids = list(db.scalars(select(AuditRun.id).where(AuditRun.cocoon_id.in_(cocoon_ids))).all())
    step_ids = list(db.scalars(select(AuditStep.id).where(AuditStep.run_id.in_(audit_run_ids))).all()) if audit_run_ids else []
    message_ids = list(db.scalars(select(Message.id).where(Message.cocoon_id.in_(cocoon_ids))).all())
    memory_ids = list(db.scalars(select(MemoryChunk.id).where(MemoryChunk.cocoon_id.in_(cocoon_ids))).all())
    durable_job_ids = list(db.scalars(select(DurableJob.id).where(DurableJob.cocoon_id.in_(cocoon_ids))).all())
    wakeup_task_ids = list(db.scalars(select(WakeupTask.id).where(WakeupTask.cocoon_id.in_(cocoon_ids))).all())

    db.query(SessionState).filter(SessionState.cocoon_id.in_(cocoon_ids)).delete(synchronize_session=False)
    db.query(CocoonTagBinding).filter(CocoonTagBinding.cocoon_id.in_(cocoon_ids)).delete(synchronize_session=False)
    db.query(Checkpoint).filter(Checkpoint.cocoon_id.in_(cocoon_ids)).delete(synchronize_session=False)
    if wakeup_task_ids:
        db.query(PluginDispatchRecord).filter(
            PluginDispatchRecord.wakeup_task_id.in_(wakeup_task_ids)
        ).delete(synchronize_session=False)
    db.query(WakeupTask).filter(WakeupTask.cocoon_id.in_(cocoon_ids)).delete(synchronize_session=False)
    db.query(CocoonPullJob).filter(
        (CocoonPullJob.source_cocoon_id.in_(cocoon_ids)) | (CocoonPullJob.target_cocoon_id.in_(cocoon_ids))
    ).delete(synchronize_session=False)
    db.query(CocoonMergeJob).filter(
        (CocoonMergeJob.source_cocoon_id.in_(cocoon_ids)) | (CocoonMergeJob.target_cocoon_id.in_(cocoon_ids))
    ).delete(synchronize_session=False)
    db.query(DurableJob).filter(DurableJob.id.in_(durable_job_ids)).delete(synchronize_session=False)

    if memory_ids:
        db.query(MemoryTag).filter(MemoryTag.memory_chunk_id.in_(memory_ids)).delete(synchronize_session=False)
        db.query(MemoryEmbedding).filter(MemoryEmbedding.memory_chunk_id.in_(memory_ids)).delete(synchronize_session=False)
        db.query(MemoryChunk).filter(MemoryChunk.id.in_(memory_ids)).delete(synchronize_session=False)

    outbox_filters = []
    if message_ids:
        outbox_filters.append(PluginImDeliveryOutbox.message_id.in_(message_ids))
    if action_ids:
        outbox_filters.append(PluginImDeliveryOutbox.action_id.in_(action_ids))
    if outbox_filters:
        db.query(PluginImDeliveryOutbox).filter(or_(*outbox_filters)).delete(synchronize_session=False)

    if message_ids:
        db.query(MessageTag).filter(MessageTag.message_id.in_(message_ids)).delete(synchronize_session=False)
        db.query(Message).filter(Message.id.in_(message_ids)).delete(synchronize_session=False)

    if step_ids:
        db.query(AuditLink).filter(
            (AuditLink.source_step_id.in_(step_ids)) | (AuditLink.target_step_id.in_(step_ids))
        ).delete(synchronize_session=False)

    if audit_run_ids:
        artifact_ids = list(
            db.scalars(select(AuditArtifact.id).where(AuditArtifact.run_id.in_(audit_run_ids))).all()
        )
        if artifact_ids:
            db.query(AuditLink).filter(
                (AuditLink.source_artifact_id.in_(artifact_ids)) | (AuditLink.target_artifact_id.in_(artifact_ids))
            ).delete(synchronize_session=False)
            db.query(AuditArtifact).filter(AuditArtifact.id.in_(artifact_ids)).delete(synchronize_session=False)
        db.query(AuditStep).filter(AuditStep.run_id.in_(audit_run_ids)).delete(synchronize_session=False)
        db.query(AuditRun).filter(AuditRun.id.in_(audit_run_ids)).delete(synchronize_session=False)

    if action_ids:
        db.query(FailedRound).filter(
            (FailedRound.cocoon_id.in_(cocoon_ids)) | (FailedRound.action_id.in_(action_ids))
        ).delete(synchronize_session=False)
        db.query(ActionDispatch).filter(ActionDispatch.id.in_(action_ids)).delete(synchronize_session=False)
    else:
        db.query(FailedRound).filter(FailedRound.cocoon_id.in_(cocoon_ids)).delete(synchronize_session=False)

    db.query(Cocoon).filter(Cocoon.id.in_(cocoon_ids)).delete(synchronize_session=False)
    db.flush()


@router.get("", response_model=list[CocoonOut])
def list_cocoons(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> list[Cocoon]:
    items = list(db.scalars(select(Cocoon).order_by(Cocoon.created_at.asc())).all())
    return db.info["container"].authorization_service.filter_visible_cocoons(db, user, items)


@router.post("", response_model=CocoonOut)
def create_cocoon(
    payload: CocoonCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> Cocoon:
    settings = db.info["container"].system_settings_service.get_settings(db)
    db.info["container"].system_settings_service.require_model_allowed(db, payload.selected_model_id)
    if payload.parent_id is None:
        existing_root = db.scalar(
            select(Cocoon).where(
                Cocoon.owner_user_id == user.id,
                Cocoon.character_id == payload.character_id,
                Cocoon.parent_id.is_(None),
            )
        )
        if existing_root:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A root cocoon already exists for this user and character",
            )
    cocoon = Cocoon(
        name=payload.name,
        character_id=payload.character_id,
        selected_model_id=payload.selected_model_id,
        parent_id=payload.parent_id,
        owner_user_id=user.id,
        default_temperature=(
            payload.default_temperature
            if payload.default_temperature is not None
            else settings.default_cocoon_temperature
        ),
        max_context_messages=(
            payload.max_context_messages
            if payload.max_context_messages is not None
            else settings.default_max_context_messages
        ),
        auto_compaction_enabled=(
            payload.auto_compaction_enabled
            if payload.auto_compaction_enabled is not None
            else settings.default_auto_compaction_enabled
        ),
    )
    db.add(cocoon)
    db.flush()
    ensure_session_state(db, cocoon_id=cocoon.id)
    return cocoon


@router.patch("/{cocoon_id}", response_model=CocoonOut)
def update_cocoon(
    cocoon_id: str,
    payload: CocoonUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> Cocoon:
    cocoon = db.info["container"].authorization_service.require_cocoon_access(
        db,
        user,
        cocoon_id,
        write=True,
    )
    for field in (
        "name",
        "character_id",
        "selected_model_id",
        "default_temperature",
        "max_context_messages",
        "auto_compaction_enabled",
    ):
        value = getattr(payload, field)
        if value is not None:
            if field == "selected_model_id":
                db.info["container"].system_settings_service.require_model_allowed(db, value)
            setattr(cocoon, field, value)
    db.flush()
    return cocoon


@router.get("/tree", response_model=list[CocoonTreeNode])
def cocoon_tree(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> list[CocoonTreeNode]:
    items = list(db.scalars(select(Cocoon).order_by(Cocoon.created_at.asc())).all())
    items = db.info["container"].authorization_service.filter_visible_cocoons(db, user, items)
    return db.info["container"].cocoon_tree_service.build_tree(items)


@router.get("/{cocoon_id}", response_model=CocoonOut)
def get_cocoon(
    cocoon_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> Cocoon:
    return db.info["container"].authorization_service.require_cocoon_access(
        db,
        user,
        cocoon_id,
        write=False,
    )


@router.get("/{cocoon_id}/state", response_model=SessionStateOut)
def get_cocoon_session_state(
    cocoon_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> SessionState:
    db.info["container"].authorization_service.require_cocoon_access(db, user, cocoon_id, write=False)
    state = load_session_state(db, cocoon_id=cocoon_id)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session state not found")
    return state


@router.get("/{cocoon_id}/wakeups", response_model=list[WakeupTaskOut])
def list_cocoon_wakeups(
    cocoon_id: str,
    status: str | None = None,
    only_ai: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> list[WakeupTaskOut]:
    db.info["container"].authorization_service.require_cocoon_access(db, user, cocoon_id, write=False)
    tasks = list_wakeup_tasks(
        db,
        cocoon_id=cocoon_id,
        status=status,
        only_ai=only_ai,
        limit=limit,
    )
    return [serialize_wakeup_task(db, task) for task in tasks]


@router.delete("/{cocoon_id}", response_model=CocoonOut)
def delete_cocoon(
    cocoon_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> Cocoon:
    cocoon = db.info["container"].authorization_service.require_cocoon_access(
        db,
        user,
        cocoon_id,
        write=True,
    )
    subtree_ids = _collect_cocoon_subtree_ids(db, cocoon.id)
    _delete_cocoon_subtree(db, subtree_ids)
    return cocoon
