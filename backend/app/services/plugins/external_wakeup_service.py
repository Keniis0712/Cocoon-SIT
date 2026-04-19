from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatGroupRoom, Cocoon, PluginDefinition, PluginDispatchRecord, PluginEventConfig, PluginVersion
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
    ) -> str | None:
        if plugin.status != "enabled":
            return None
        event_config = session.scalar(
            select(PluginEventConfig).where(
                PluginEventConfig.plugin_id == plugin.id,
                PluginEventConfig.event_name == event_name,
            )
        )
        if event_config and not event_config.is_enabled:
            return None

        target_type = str(envelope.get("target_type") or "").strip()
        target_id = str(envelope.get("target_id") or "").strip()
        summary = str(envelope.get("summary") or "").strip()
        dedupe_key = envelope.get("dedupe_key")
        payload = dict(envelope.get("payload") or {})
        if target_type not in {"cocoon", "chat_group"}:
            raise ValueError("External plugin event target_type must be 'cocoon' or 'chat_group'")
        if not target_id:
            raise ValueError("External plugin event target_id is required")
        if not summary:
            raise ValueError("External plugin event summary is required")
        if target_type == "cocoon":
            if not session.get(Cocoon, target_id):
                raise ValueError(f"Unknown cocoon target: {target_id}")
        else:
            if not session.get(ChatGroupRoom, target_id):
                raise ValueError(f"Unknown chat_group target: {target_id}")

        if dedupe_key:
            existing = session.scalar(
                select(PluginDispatchRecord).where(
                    PluginDispatchRecord.plugin_id == plugin.id,
                    PluginDispatchRecord.event_name == event_name,
                    PluginDispatchRecord.dedupe_key == str(dedupe_key),
                )
            )
            if existing:
                return existing.wakeup_task_id

        wakeup_payload = {
            "source_kind": "plugin",
            "plugin_id": plugin.id,
            "plugin_version": version.version,
            "plugin_event": event_name,
            "external_payload": payload,
            "summary": summary,
            "dedupe_key": str(dedupe_key) if dedupe_key is not None else None,
        }
        task, _ = self.scheduler_node.schedule_wakeup(
            session,
            cocoon_id=target_id if target_type == "cocoon" else None,
            chat_group_id=target_id if target_type == "chat_group" else None,
            run_at=datetime.now(UTC).replace(tzinfo=None),
            reason=summary,
            payload_json=wakeup_payload,
        )
        record = PluginDispatchRecord(
            plugin_id=plugin.id,
            plugin_version_id=version.id,
            event_name=event_name,
            target_type=target_type,
            target_id=target_id,
            dedupe_key=str(dedupe_key) if dedupe_key is not None else None,
            wakeup_task_id=task.id,
            payload_json={"envelope": envelope},
        )
        session.add(record)
        session.flush()
        return task.id
