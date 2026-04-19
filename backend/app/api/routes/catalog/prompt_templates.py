from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_permission
from app.models import User
from app.schemas.catalog.prompts import (
    PromptTemplateDetail,
    PromptTemplateUpsertRequest,
    PromptTemplateOut,
)


router = APIRouter()


@router.get("", response_model=list[PromptTemplateDetail])
def list_prompt_templates(
    db: Session = Depends(get_db),
    _=Depends(require_permission("prompt_templates:read")),
) -> list[PromptTemplateDetail]:
    return db.info["container"].prompt_template_admin_service.list_templates(db)


@router.post("/{template_type}", response_model=PromptTemplateOut)
def create_prompt_template(
    template_type: str,
    payload: PromptTemplateUpsertRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("prompt_templates:write")),
) -> PromptTemplateOut:
    return db.info["container"].prompt_template_admin_service.upsert_template(db, template_type, payload, user)


@router.put("/{template_type}", response_model=PromptTemplateOut)
def update_prompt_template(
    template_type: str,
    payload: PromptTemplateUpsertRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("prompt_templates:write")),
) -> PromptTemplateOut:
    return db.info["container"].prompt_template_admin_service.upsert_template(db, template_type, payload, user)


@router.post("/{template_type}/reset", response_model=PromptTemplateOut)
def reset_prompt_template(
    template_type: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_permission("prompt_templates:write")),
) -> PromptTemplateOut:
    return db.info["container"].prompt_template_admin_service.reset_template(db, template_type, user)
