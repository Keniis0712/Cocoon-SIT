from __future__ import annotations

from datetime import UTC, datetime
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ChatGroupRoom,
    Cocoon,
    PluginChatGroupConfig,
    PluginDefinition,
    PluginDispatchRecord,
    PluginEventConfig,
    PluginGroupVisibility,
    PluginTargetBinding,
    PluginUserConfig,
    PluginVersion,
    UserGroupMember,
)
from app.services.runtime.scheduling.scheduler_node import SchedulerNode

logger = logging.getLogger(__name__)


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
        scope_type: str | None = None,
        scope_id: str | None = None,
    ) -> list[str]:
        if plugin.status != "enabled":
            logger.info(
                "Plugin wakeup ingest skipped plugin_id=%s plugin_name=%s event_name=%s reason=plugin_not_enabled status=%s",
                plugin.id,
                plugin.name,
                event_name,
                plugin.status,
            )
            return []
        event_config = session.scalar(
            select(PluginEventConfig).where(
                PluginEventConfig.plugin_id == plugin.id,
                PluginEventConfig.event_name == event_name,
            )
        )
        if event_config and not event_config.is_enabled:
            logger.info(
                "Plugin wakeup ingest skipped plugin_id=%s plugin_name=%s event_name=%s reason=event_disabled",
                plugin.id,
                plugin.name,
                event_name,
            )
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
        skip_counts = {
            "scope_type": 0,
            "scope_id": 0,
            "chat_group_visibility": 0,
            "missing_user": 0,
            "user_visibility": 0,
        }
        bindings = list(
            session.scalars(
                select(PluginTargetBinding)
                .where(PluginTargetBinding.plugin_id == plugin.id)
                .order_by(PluginTargetBinding.created_at.asc())
            ).all()
        )
        logger.info(
            "Plugin wakeup ingest started plugin_id=%s plugin_name=%s event_name=%s binding_count=%s scope_type=%s scope_id=%s",
            plugin.id,
            plugin.name,
            event_name,
            len(bindings),
            scope_type,
            scope_id,
        )
        for binding in bindings:
            if scope_type and binding.scope_type != scope_type:
                skip_counts["scope_type"] += 1
                continue
            if scope_id and binding.scope_id != scope_id:
                skip_counts["scope_id"] += 1
                continue
            if binding.scope_type == "chat_group" and not self._can_deliver_to_chat_group(session, plugin, binding.scope_id):
                skip_counts["chat_group_visibility"] += 1
                continue
            target_user_id = self._resolve_target_user_id(session, binding)
            if binding.scope_type == "user" and not target_user_id:
                skip_counts["missing_user"] += 1
                continue
            if binding.scope_type == "user" and not self._can_deliver_to_user(session, plugin, binding.scope_id):
                skip_counts["user_visibility"] += 1
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
                wakeup_task_id=task.id,
                payload_json={"envelope": envelope, "target_binding_id": binding.id},
            )
            session.add(record)
            task_ids.append(task.id)
            logger.info(
                "Plugin wakeup scheduled plugin_id=%s event_name=%s binding_id=%s target_type=%s target_id=%s wakeup_task_id=%s",
                plugin.id,
                event_name,
                binding.id,
                binding.target_type,
                binding.target_id,
                task.id,
            )
        session.flush()
        logger.info(
            "Plugin wakeup ingest finished plugin_id=%s plugin_name=%s event_name=%s wakeup_task_count=%s skip_counts=%s",
            plugin.id,
            plugin.name,
            event_name,
            len(task_ids),
            skip_counts,
        )
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

    def _can_deliver_to_chat_group(self, session: Session, plugin: PluginDefinition, chat_group_id: str) -> bool:
        if not session.get(ChatGroupRoom, chat_group_id):
            return False
        group_config = session.scalar(
            select(PluginChatGroupConfig).where(
                PluginChatGroupConfig.plugin_id == plugin.id,
                PluginChatGroupConfig.chat_group_id == chat_group_id,
            )
        )
        if group_config and not group_config.is_enabled:
            return False
        if group_config and group_config.error_text:
            return False
        return True
