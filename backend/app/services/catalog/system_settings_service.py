"""Mutable system settings backed by a singleton database row."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AvailableModel, SystemSettings, User
from app.schemas.catalog.settings import SystemSettingsUpdate
from app.services.security.rbac import get_role_for_user


class SystemSettingsService:
    """Loads, creates, updates, and interprets global runtime settings."""

    DEFAULT_ROW_ID = "default"
    DEFAULT_MEMORY_PROFILES = {
        "reply_only": {
            "request_mode": "reply_only",
            "read_long_term_memory": True,
            "read_fact_cache": True,
            "vector_recall_limit": 20,
            "prompt_memory_limit": 5,
            "tag_match_weight": 0.05,
            "vector_weight": 0.45,
            "importance_weight": 0.25,
            "recency_weight": 0.15,
            "confidence_weight": 0.10,
            "candidate_promote_hits": 2,
            "candidate_ttl_hours": 72,
            "fact_cache_ttl_minutes": 120,
            "maintenance_decay_days": 90,
            "maintenance_decay_factor": 0.95,
            "archive_after_days": 180,
            "access_importance_boost": 0.02,
        },
        "single_pass": {
            "request_mode": "single_pass",
            "read_long_term_memory": True,
            "read_fact_cache": True,
            "vector_recall_limit": 20,
            "prompt_memory_limit": 5,
            "tag_match_weight": 0.05,
            "vector_weight": 0.45,
            "importance_weight": 0.25,
            "recency_weight": 0.15,
            "confidence_weight": 0.10,
            "candidate_promote_hits": 2,
            "candidate_ttl_hours": 72,
            "fact_cache_ttl_minutes": 120,
            "maintenance_decay_days": 90,
            "maintenance_decay_factor": 0.95,
            "archive_after_days": 180,
            "access_importance_boost": 0.02,
        },
        "meta_reply": {
            "request_mode": "meta_reply",
            "read_long_term_memory": True,
            "read_fact_cache": True,
            "vector_recall_limit": 20,
            "prompt_memory_limit": 5,
            "tag_match_weight": 0.05,
            "vector_weight": 0.45,
            "importance_weight": 0.25,
            "recency_weight": 0.15,
            "confidence_weight": 0.10,
            "candidate_promote_hits": 2,
            "candidate_ttl_hours": 72,
            "fact_cache_ttl_minutes": 120,
            "maintenance_decay_days": 90,
            "maintenance_decay_factor": 0.95,
            "archive_after_days": 180,
            "access_importance_boost": 0.02,
        },
    }

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_settings(self, session: Session) -> SystemSettings:
        """Return the singleton settings row, creating it lazily when needed."""
        current = session.get(SystemSettings, self.DEFAULT_ROW_ID)
        if current:
            return current

        current = SystemSettings(
            id=self.DEFAULT_ROW_ID,
            allow_registration=False,
            max_chat_turns=0,
            allowed_model_ids_json=[],
            default_cocoon_temperature=0.7,
            default_max_context_messages=12,
            default_auto_compaction_enabled=True,
            private_chat_debounce_seconds=2,
            group_chat_debounce_seconds=2,
            rollback_retention_days=30,
            rollback_cleanup_interval_hours=24,
            default_memory_profile="meta_reply",
            memory_profiles_json=self.DEFAULT_MEMORY_PROFILES,
        )
        session.add(current)
        session.flush()
        return current

    def update_settings(self, session: Session, payload: SystemSettingsUpdate) -> SystemSettings:
        """Patch the singleton settings row."""
        current = self.get_settings(session)
        updates = payload.model_dump(exclude_unset=True)

        if "allowed_model_ids" in updates:
            allowed_ids = updates.pop("allowed_model_ids") or []
            if allowed_ids:
                known_ids = {
                    item
                    for item in session.scalars(
                        select(AvailableModel.id).where(AvailableModel.id.in_(allowed_ids))
                    ).all()
                }
                missing_ids = [item for item in allowed_ids if item not in known_ids]
                if missing_ids:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Unknown allowed model ids: {', '.join(missing_ids)}",
                    )
            current.allowed_model_ids_json = allowed_ids

        for field, value in updates.items():
            setattr(current, field, value)

        if not current.memory_profiles_json:
            current.memory_profiles_json = self.DEFAULT_MEMORY_PROFILES
        if not current.default_memory_profile:
            current.default_memory_profile = "meta_reply"

        session.flush()
        return current

    def get_memory_profiles(self, session: Session) -> dict[str, dict]:
        current = self.get_settings(session)
        configured = current.memory_profiles_json or {}
        merged = {name: dict(values) for name, values in self.DEFAULT_MEMORY_PROFILES.items()}
        for name, values in configured.items():
            if not isinstance(values, dict):
                continue
            merged[name] = {**merged.get(name, {}), **values}
        return merged

    def get_memory_profile(self, session: Session, profile_name: str | None) -> dict:
        current = self.get_settings(session)
        profiles = self.get_memory_profiles(session)
        candidate = str(profile_name or current.default_memory_profile or "meta_reply").strip()
        return profiles.get(candidate, profiles["meta_reply"]) | {"name": candidate if candidate in profiles else "meta_reply"}

    def require_model_allowed(self, session: Session, model_id: str) -> None:
        """Raise when a model is not part of the configured whitelist."""
        current = self.get_settings(session)
        allowed_ids = current.allowed_model_ids_json or []
        if allowed_ids and model_id not in allowed_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected model is not allowed by system settings",
            )

    def list_allowed_models(self, session: Session) -> list[AvailableModel]:
        """Return whitelisted models in the configured order."""
        current = self.get_settings(session)
        allowed_ids = current.allowed_model_ids_json or []
        if not allowed_ids:
            return []

        models = {
            item.id: item
            for item in session.scalars(
                select(AvailableModel).where(AvailableModel.id.in_(allowed_ids))
            ).all()
        }
        return [models[item_id] for item_id in allowed_ids if item_id in models]

    def is_admin_user(self, session: Session, user: User) -> bool:
        role = get_role_for_user(session, user)
        return bool(role and role.name == "admin")

    def filter_visible_models(self, session: Session, user: User, models: list[AvailableModel]) -> list[AvailableModel]:
        current = self.get_settings(session)
        allowed_ids = set(current.allowed_model_ids_json or [])
        if not allowed_ids or self.is_admin_user(session, user):
            return models
        return [model for model in models if model.id in allowed_ids]
