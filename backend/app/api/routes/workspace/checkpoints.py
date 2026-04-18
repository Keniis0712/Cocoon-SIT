from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.models import Checkpoint, Message
from app.schemas.workspace.checkpoints import CheckpointOut


router = APIRouter()


class CheckpointCreate(BaseModel):
    cocoon_id: str
    anchor_message_id: str
    label: str


@router.get("/{cocoon_id}", response_model=list[CheckpointOut])
def list_checkpoints(
    cocoon_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("checkpoints:read")),
) -> list[Checkpoint]:
    db.info["container"].authorization_service.require_cocoon_access(db, user, cocoon_id, write=False)
    return list(
        db.scalars(
            select(Checkpoint)
            .where(Checkpoint.cocoon_id == cocoon_id)
            .order_by(Checkpoint.created_at.desc())
        ).all()
    )


@router.post("", response_model=CheckpointOut)
def create_checkpoint(
    payload: CheckpointCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("checkpoints:write")),
) -> Checkpoint:
    db.info["container"].authorization_service.require_cocoon_access(db, user, payload.cocoon_id, write=True)
    message = db.get(Message, payload.anchor_message_id)
    if not message or message.cocoon_id != payload.cocoon_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anchor message not found")
    checkpoint = Checkpoint(
        cocoon_id=payload.cocoon_id,
        anchor_message_id=payload.anchor_message_id,
        label=payload.label,
    )
    db.add(checkpoint)
    db.flush()
    return checkpoint
