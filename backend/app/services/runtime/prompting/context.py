from __future__ import annotations

from typing import Any

from app.services.runtime.prompting.helpers import (
    _compact_pending_wakeup_payload,
    _compact_runtime_event_payload,
    _compact_wakeup_context_payload,
    _mentionable_for_target,
    _sanitize_prompt_dict,
    _sanitize_prompt_value,
    _sanitize_provider_capabilities,
    _serialize_tags,
    _tag_catalog,
    _tag_names,
    build_runtime_clock_payload,
)
from app.services.runtime.types import ContextPackage


def build_structured_prompt_context(
    context: ContextPackage,
    snapshot: dict[str, Any],
    *,
    include_session_state: bool = False,
    generation_brief: str | None = None,
) -> tuple[dict[str, Any], str]:
    clock = build_runtime_clock_payload(context)
    runtime_event = _compact_runtime_event_payload(snapshot.get("runtime_event"))
    if "timezone" not in runtime_event:
        runtime_event["timezone"] = clock["timezone"]
    compact_payload: dict[str, Any] = {
        "runtime_event": runtime_event,
        "current_time": clock,
    }
    lines = [
        "RUNTIME_CONTEXT_START",
        f"Current local time: {clock['local_time']} ({clock['timezone']})",
        (
            f"Event: {runtime_event.get('event_type', 'unknown')} -> "
            f"{runtime_event.get('target_type', context.target_type)}"
        ),
    ]
    if runtime_event.get("reason"):
        lines.append(f"Event reason: {runtime_event['reason']}")
    if runtime_event.get("trigger_kind"):
        lines.append(f"Trigger kind: {runtime_event['trigger_kind']}")
    if runtime_event.get("scheduled_by"):
        lines.append(f"Scheduled by: {runtime_event['scheduled_by']}")
    if runtime_event.get("source_event_type"):
        lines.append(f"Source event type: {runtime_event['source_event_type']}")

    wakeup_context = _compact_wakeup_context_payload(snapshot.get("wakeup_context"))
    if wakeup_context:
        compact_payload["wakeup_context"] = wakeup_context
        if wakeup_context.get("reason"):
            lines.append(f"Wakeup reason: {wakeup_context['reason']}")
        if wakeup_context.get("idle_summary"):
            lines.append(f"Wakeup summary: {wakeup_context['idle_summary']}")

    pending_wakeups = _compact_pending_wakeup_payload(snapshot.get("pending_wakeups"))
    compact_payload["pending_wakeups"] = pending_wakeups
    if pending_wakeups:
        lines.append(
            "Pending wakeups: "
            + "; ".join(
                (
                    f"{item.get('id', 'unknown')} at {item.get('run_at', 'unknown')} "
                    f"({item.get('reason', 'no reason')})"
                )
                for item in pending_wakeups
            )
        )
    else:
        lines.append("Pending wakeups: none")

    if include_session_state:
        session_state = (
            snapshot.get("session_state") if isinstance(snapshot.get("session_state"), dict) else {}
        )
        prompt_tag_catalog = (
            snapshot.get("tag_catalog") if isinstance(snapshot.get("tag_catalog"), list) else []
        )
        compact_session_state = {
            "relation_score": session_state.get("relation_score"),
            "persona": session_state.get("persona"),
            "active_tags": _tag_names(session_state.get("active_tags")),
        }
        compact_payload["session_state"] = {
            key: value
            for key, value in compact_session_state.items()
            if value not in (None, "", [], {})
        }
        if compact_session_state.get("relation_score") is not None:
            lines.append(f"Relation score: {compact_session_state['relation_score']}")
        if compact_session_state.get("persona"):
            lines.append(
                "Persona state: "
                + str(
                    compact_session_state["persona"]
                    if isinstance(compact_session_state["persona"], str)
                    else _sanitize_prompt_value(compact_session_state["persona"])
                )
            )
        tag_names = compact_session_state.get("active_tags") or []
        lines.append(f"Active tags: {', '.join(tag_names) if tag_names else 'none'}")
        if prompt_tag_catalog:
            lines.append(
                "Allowed tag indexes: "
                + "; ".join(
                    f"{item.get('index')}={item.get('tag_id')}"
                    for item in prompt_tag_catalog
                    if isinstance(item, dict)
                )
            )

    if generation_brief:
        compact_payload["generation_brief"] = generation_brief
        lines.append(f"Generation focus: {generation_brief}")

    lines.append("RUNTIME_CONTEXT_END")
    return compact_payload, "\n".join(lines)


def _character_settings_payload(context: ContextPackage) -> dict[str, Any]:
    payload = dict(context.character.settings_json or {})
    prompt_summary = (context.character.prompt_summary or "").strip()
    personality_prompt = str(payload.get("personality_prompt") or "").strip()
    if prompt_summary and prompt_summary != personality_prompt:
        payload["prompt_summary"] = prompt_summary
    elif (
        "prompt_summary" in payload
        and str(payload.get("prompt_summary") or "").strip() == personality_prompt
    ):
        payload.pop("prompt_summary", None)
    return payload


def _participant_alias(context: ContextPackage, sender_user_id: str | None) -> str | None:
    if not sender_user_id:
        return None
    sender = str(sender_user_id)
    if context.target_type == "cocoon":
        return "you"
    participants: dict[str, str] = {}
    next_index = 1
    for message in context.visible_messages:
        user_id = getattr(message, "sender_user_id", None)
        if message.role != "user" or not user_id:
            continue
        normalized = str(user_id)
        if normalized not in participants:
            participants[normalized] = f"participant_{next_index}"
            next_index += 1
    return participants.get(sender, "participant")


def _runtime_message_payload(
    message, context: ContextPackage, catalog: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    tag_refs = [
        tag_ref for tag_ref in list(message.tags_json or []) if not bool((catalog.get(tag_ref) or {}).get("is_system"))
    ]
    retracted_suffix = (
        "\n\n[system note: this message was later retracted]" if message.is_retracted else ""
    )
    payload = {
        "role": message.role,
        "content": f"{message.content}{retracted_suffix}",
        "is_retracted": message.is_retracted,
        "tags": _serialize_tags(tag_refs, context, catalog),
        "mentionable_in_current_target": _mentionable_for_target(tag_refs, context, catalog),
    }
    if alias := _participant_alias(context, getattr(message, "sender_user_id", None)):
        payload["speaker"] = alias
    return payload


def _runtime_memory_payload(
    memory, context: ContextPackage, catalog: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    tag_refs = [
        tag_ref for tag_ref in list(memory.tags_json or []) if not bool((catalog.get(tag_ref) or {}).get("is_system"))
    ]
    return {
        "scope": memory.scope,
        "summary": memory.summary,
        "content": memory.content,
        "tags": _serialize_tags(tag_refs, context, catalog),
        "mentionable_in_current_target": _mentionable_for_target(tag_refs, context, catalog),
        "source": "chat_group" if memory.chat_group_id else "cocoon",
    }


def _merge_context_payload(
    context: ContextPackage, catalog: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    payload = context.external_context.get("merge_context")
    if not isinstance(payload, dict):
        return payload
    source_state = payload.get("source_state")
    source_state_payload = source_state if isinstance(source_state, dict) else {}
    source_active_tags = source_state_payload.get("active_tags_json")
    tag_refs = (
        [
            tag_ref
            for tag_ref in source_active_tags
            if not bool((catalog.get(tag_ref) or {}).get("is_system"))
        ]
        if isinstance(source_active_tags, list)
        else []
    )
    return {
        **_sanitize_prompt_dict(payload),
        "source_state": {
            "relation_score": source_state_payload.get("relation_score", 0),
            "persona_json": _sanitize_prompt_value(source_state_payload.get("persona_json", {})),
            "active_tags": _serialize_tags(tag_refs, context, catalog),
        },
    }


def _runtime_event_payload(context: ContextPackage) -> dict[str, Any]:
    return {
        "event_type": context.runtime_event.event_type,
        "target_type": context.runtime_event.target_type,
        **_sanitize_prompt_dict(context.runtime_event.payload),
    }


def _prompt_tag_catalog(context: ContextPackage) -> list[dict[str, Any]]:
    payload = context.external_context.get("prompt_tag_catalog")
    if not isinstance(payload, list):
        return []
    sanitized: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        sanitized.append(
            {
                "index": item.get("index"),
                "tag_id": item.get("tag_id"),
                "brief": item.get("brief"),
            }
        )
    return sanitized


def _pending_wakeup_payload(tasks: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        item = {
            "id": task.get("id"),
            "run_at": task.get("run_at"),
            "reason": task.get("reason"),
            "status": task.get("status"),
            "has_payload": bool(task.get("payload_json")),
        }
        if task.get("cancelled_at"):
            item["cancelled_at"] = task.get("cancelled_at")
        sanitized.append(item)
    return sanitized


def build_provider_message_payload(message, context: ContextPackage) -> dict[str, str]:
    content = message.content
    if message.role == "user" and (
        alias := _participant_alias(context, getattr(message, "sender_user_id", None))
    ):
        content = f"[speaker:{alias}] {content}"
    if message.is_retracted:
        content = f"{content}\n\n[system note: this message was later retracted]"
    return {"role": message.role, "content": content}


def build_runtime_prompt_variables(
    context: ContextPackage,
    *,
    provider_capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    catalog = _tag_catalog(context)
    pending_wakeups = _pending_wakeup_payload(context.external_context.get("pending_wakeups", []))
    return {
        "character_settings": _character_settings_payload(context),
        "conversation_target": {
            "type": context.target_type,
            "name": context.cocoon.name,
        },
        "session_state": {
            "relation_score": context.session_state.relation_score,
            "persona": context.session_state.persona_json,
            "active_tags": _serialize_tags(
                [
                    tag_ref
                    for tag_ref in list(context.session_state.active_tags_json or [])
                    if not bool((catalog.get(tag_ref) or {}).get("is_system"))
                ],
                context,
                catalog,
            ),
            "tag_catalog": _prompt_tag_catalog(context),
        },
        "tag_catalog": _prompt_tag_catalog(context),
        "visible_messages": [
            _runtime_message_payload(message, context, catalog)
            for message in context.visible_messages
        ],
        "memory_context": [
            _runtime_memory_payload(memory, context, catalog) for memory in context.memory_context
        ],
        "runtime_event": _runtime_event_payload(context),
        "current_time": build_runtime_clock_payload(context),
        "wakeup_context": _sanitize_prompt_value(context.external_context.get("wakeup_context")),
        "pending_wakeups": pending_wakeups,
        "merge_context": _merge_context_payload(context, catalog),
        "provider_capabilities": _sanitize_provider_capabilities(provider_capabilities),
    }
