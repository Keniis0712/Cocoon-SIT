from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models import Role
from app.schemas.access.auth import RoleCreate, RoleOut, RoleUpdate


router = APIRouter()


@router.get("", response_model=list[RoleOut])
def list_roles(
    db: Session = Depends(get_db),
    _=Depends(require_permission("roles:read")),
) -> list[Role]:
    return db.info["container"].role_service.list_roles(db)


@router.post("", response_model=RoleOut)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("roles:write")),
) -> Role:
    return db.info["container"].role_service.create_role(db, payload)


@router.patch("/{role_id}", response_model=RoleOut)
def update_role(
    role_id: str,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("roles:write")),
) -> Role:
    return db.info["container"].role_service.update_role(db, role_id, payload)
