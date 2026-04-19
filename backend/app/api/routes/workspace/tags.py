from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.models import CocoonTagBinding
from app.schemas.workspace.cocoons import CocoonTagBindRequest
from app.schemas.workspace.tags import CocoonTagBindingOut, CocoonTagBindResult


router = APIRouter()


@router.get("/{cocoon_id}/tags", response_model=list[CocoonTagBindingOut])
def list_cocoon_tags(
    cocoon_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("cocoons:read")),
) -> list[CocoonTagBinding]:
    db.info["container"].authorization_service.require_cocoon_access(db, user, cocoon_id, write=False)
    bindings = list(
        db.scalars(
            select(CocoonTagBinding)
            .where(CocoonTagBinding.cocoon_id == cocoon_id)
            .order_by(CocoonTagBinding.created_at.asc())
        ).all()
    )
    return bindings


@router.post("/{cocoon_id}/tags", response_model=CocoonTagBindResult)
def bind_cocoon_tag(
    cocoon_id: str,
    payload: CocoonTagBindRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> CocoonTagBindResult:
    db.info["container"].authorization_service.require_cocoon_access(db, user, cocoon_id, write=True)
    binding = db.info["container"].cocoon_tag_service.bind_tag(db, cocoon_id, payload.tag_id)
    return CocoonTagBindResult(binding_id=binding.id, tag_id=binding.tag_id)


@router.delete("/{cocoon_id}/tags/{tag_id}", response_model=CocoonTagBindResult)
def unbind_cocoon_tag(
    cocoon_id: str,
    tag_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    _=Depends(require_permission("cocoons:write")),
) -> CocoonTagBindResult:
    db.info["container"].authorization_service.require_cocoon_access(db, user, cocoon_id, write=True)
    binding = db.info["container"].cocoon_tag_service.unbind_tag(db, cocoon_id, tag_id)
    return CocoonTagBindResult(binding_id=binding.id, tag_id=binding.tag_id)
