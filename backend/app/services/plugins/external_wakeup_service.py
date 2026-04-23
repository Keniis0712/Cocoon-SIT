from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ChatGroupRoom,
    Cocoon,
    PluginDefinition,
    PluginDispatchRecord,
    PluginEventConfig,
    PluginGroupVisibility,
    PluginTargetBinding,
    PluginUserConfig,
    PluginVersion,
    UserGroupMember,
)
from app.services.runtime.scheduler_node import SchedulerNode


class ExternalWakeupService:
    def __init__(self, scheduler_node: SchedulerNode) -> None:
        self.scheduler_node = scheduler_node

    def ingest(
        self,
        session: Session,
        *,
        plugin: PluginDefinition,
        version: PluginVersion,
        event_name: str,
        envelope: dict,
    ) -> list[str]:
        if plugin.status != "enabled":
            return []
        event_config = session.scalar(
            select(PluginEventConfig).where(
                PluginEventConfig.plugin_id == plugin.id,
                PluginEventConfig.event_name == event_name,
            )
        )
        if event_config and not event_config.is_enabled:
            return []

        summary = str(envelope.get("summary") or "").strip()
        payload = dict(envelope.get("payload") or {})
        if not summary:
            raise ValueError("External plugin event summary is required")

        wakeup_payload = {
            "source_kind": "plugin",
            "plugin_id": plugin.id,
            "plugin_version": version.version,
            "plugin_event": event_name,
            "external_payload": payload,
            "summary": summary,
        }
        task_ids: list[str] = []
        bindings = list(
            session.scalars(
                select(PluginTargetBinding)
                .where(PluginTargetBinding.plugin_id == plugin.id)
                .order_by(PluginTargetBinding.created_at.asc())
            ).all()
        )
        for binding in bindings:
            target_user_id = self._resolve_target_user_id(session, binding)
            if not target_user_id:
                continue
            if not self._can_deliver_to_user(session, plugin, target_user_id):
                continue
            task, _ = self.scheduler_node.schedule_wakeup(
                session,
                cocoon_id=binding.target_id if binding.target_type == "cocoon" else None,
                chat_group_id=binding.target_id if binding.target_type == "chat_group" else None,
                run_at=datetime.now(UTC).replace(tzinfo=None),
                reason=summary,
                payload_json={**wakeup_payload, "target_binding_id": binding.id},
            )
            record = PluginDispatchRecord(
                plugin_id=plugin.id,
                plugin_version_id=version.id,
                event_name=event_name,
                target_type=binding.target_type,
                target_id=binding.target_id,
                dedupe_key=None,
                wakeup_task_id=task.id,
                payload_json={"envelope": envelope, "target_binding_id": binding.id},
            )
            session.add(record)
            task_ids.append(task.id)
        session.flush()
        return task_ids

    def _resolve_target_user_id(self, session: Session, binding: PluginTargetBinding) -> str | None:
        if binding.target_type == "cocoon":
            cocoon = session.get(Cocoon, binding.target_id)
            return cocoon.owner_user_id if cocoon else None
        if binding.target_type == "chat_group":
            room = session.get(ChatGroupRoom, binding.target_id)
            return room.owner_user_id if room else None
        return None

    def _can_deliver_to_user(self, session: Session, plugin: PluginDefinition, user_id: str) -> bool:
        user_config = session.scalar(
            select(PluginUserConfig).where(
                PluginUserConfig.plugin_id == plugin.id,
                PluginUserConfig.user_id == user_id,
            )
        )
        if user_config and not user_config.is_enabled:
            return False
        if user_config and user_config.error_text:
            return False

        group_ids = [
            item.group_id
            for item in session.scalars(
                select(UserGroupMember).where(UserGroupMember.user_id == user_id)
            ).all()
        ]
        if group_ids:
            overrides = list(
                session.scalars(
                    select(PluginGroupVisibility).where(
                        PluginGroupVisibility.plugin_id == plugin.id,
                        PluginGroupVisibility.group_id.in_(group_ids),
                    )
                ).all()
            )
            if overrides:
                return any(item.is_visible for item in overrides)
        return bool(plugin.is_globally_visible)
