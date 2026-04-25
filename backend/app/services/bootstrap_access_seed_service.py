from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Role, User
from app.services.access.group_service import GroupService
from app.services.security.encryption import hash_secret


class BootstrapAccessSeedService:
    """Seeds default roles and the bootstrap administrator."""

    def __init__(self, group_service: GroupService | None = None) -> None:
        self.group_service = group_service or GroupService()

    def ensure_defaults(self, session: Session, settings: Settings) -> User:
        admin_permissions = {
            "users:read": True,
            "users:write": True,
            "roles:read": True,
            "roles:write": True,
            "prompt_templates:read": True,
            "prompt_templates:write": True,
            "providers:read": True,
            "providers:write": True,
            "cocoons:read": True,
            "cocoons:write": True,
            "characters:read": True,
            "characters:write": True,
            "tags:read": True,
            "tags:write": True,
            "settings:read": True,
            "settings:write": True,
            "memory:read": True,
            "memory:write": True,
            "pulls:write": True,
            "merges:write": True,
            "checkpoints:read": True,
            "checkpoints:write": True,
            "audits:read": True,
            "insights:read": True,
            "artifacts:cleanup": True,
            "plugins:read": True,
            "plugins:write": True,
            "plugins:run": True,
        }
        admin_role = session.scalar(select(Role).where(Role.name == "admin"))
        if not admin_role:
            admin_role = Role(
                name="admin",
                permissions_json=admin_permissions,
            )
            session.add(admin_role)
            session.flush()
        else:
            admin_role.permissions_json = {**(admin_role.permissions_json or {}), **admin_permissions}

        operator_permissions = {
            "cocoons:read": True,
            "cocoons:write": True,
            "characters:read": True,
            "prompt_templates:read": True,
            "providers:read": True,
            "tags:read": True,
            "memory:read": True,
            "pulls:write": True,
            "merges:write": True,
            "checkpoints:read": True,
            "checkpoints:write": True,
            "audits:read": True,
            "insights:read": True,
        }
        operator_role = session.scalar(select(Role).where(Role.name == "operator"))
        if not operator_role:
            operator_role = Role(
                name="operator",
                permissions_json=operator_permissions,
            )
            session.add(operator_role)
            session.flush()
        else:
            operator_role.permissions_json = {**(operator_role.permissions_json or {}), **operator_permissions}

        user_permissions = {
            "cocoons:read": True,
            "cocoons:write": True,
            "characters:read": True,
            "providers:read": True,
            "tags:read": True,
            "memory:read": True,
            "checkpoints:read": True,
            "checkpoints:write": True,
        }
        user_role = session.scalar(select(Role).where(Role.name == "user"))
        if not user_role:
            user_role = Role(
                name="user",
                permissions_json=user_permissions,
            )
            session.add(user_role)
            session.flush()
        else:
            user_role.permissions_json = {**(user_role.permissions_json or {}), **user_permissions}

        admin_user = session.scalar(select(User).where(User.username == settings.default_admin_username))
        if not admin_user:
            admin_user = User(
                username=settings.default_admin_username,
                email=settings.default_admin_email,
                password_hash=hash_secret(settings.default_admin_password),
                role_id=admin_role.id,
            )
            session.add(admin_user)
            session.flush()
        else:
            admin_user.role_id = admin_role.id
            admin_user.is_active = True
        self.group_service.ensure_root_group(session)
        return admin_user
