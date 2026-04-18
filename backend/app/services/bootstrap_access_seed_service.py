from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Role, User
from app.services.security.encryption import hash_secret


class BootstrapAccessSeedService:
    """Seeds default roles and the bootstrap administrator."""

    def ensure_defaults(self, session: Session, settings: Settings) -> User:
        admin_role = session.scalar(select(Role).where(Role.name == "admin"))
        if not admin_role:
            admin_role = Role(
                name="admin",
                permissions_json={
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
                    "memory:read": True,
                    "memory:write": True,
                    "wakeup:write": True,
                    "pulls:write": True,
                    "merges:write": True,
                    "checkpoints:read": True,
                    "checkpoints:write": True,
                    "audits:read": True,
                    "insights:read": True,
                    "artifacts:cleanup": True,
                },
            )
            session.add(admin_role)
            session.flush()

        operator_role = session.scalar(select(Role).where(Role.name == "operator"))
        if not operator_role:
            operator_role = Role(
                name="operator",
                permissions_json={
                    "cocoons:read": True,
                    "cocoons:write": True,
                    "characters:read": True,
                    "prompt_templates:read": True,
                    "providers:read": True,
                    "tags:read": True,
                    "memory:read": True,
                    "wakeup:write": True,
                    "pulls:write": True,
                    "merges:write": True,
                    "checkpoints:read": True,
                    "checkpoints:write": True,
                    "audits:read": True,
                    "insights:read": True,
                },
            )
            session.add(operator_role)
            session.flush()

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
        return admin_user
