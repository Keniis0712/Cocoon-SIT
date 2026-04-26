from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any


PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")
SENSITIVE_KEYS = {"secret", "token", "api_key", "password", "secret_encrypted"}


def sanitize_snapshot(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in SENSITIVE_KEYS:
                result[key] = "***redacted***"
            else:
                result[key] = sanitize_snapshot(item)
        return result
    if isinstance(value, list):
        return [sanitize_snapshot(item) for item in value]
    return value


def find_placeholders(content: str) -> list[str]:
    return sorted(set(PLACEHOLDER_RE.findall(content)))


def _stringify_scalar(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _indent_block(text: str, indent: int) -> str:
    prefix = " " * indent
    return "\n".join(f"{prefix}{line}" if line else prefix for line in text.splitlines())


def _format_mapping(value: Mapping[str, Any], indent: int) -> str:
    if not value:
        return "{}"
    lines: list[str] = []
    for key, item in value.items():
        label = f"{' ' * indent}{key}:"
        rendered = _format_prompt_value(item, indent + 2)
        if isinstance(item, (Mapping, list)) or "\n" in rendered:
            lines.append(label)
            lines.append(_indent_block(rendered, indent + 2))
            continue
        lines.append(f"{label} {rendered}")
    return "\n".join(lines)


def _format_sequence(value: list[Any], indent: int) -> str:
    if not value:
        return "[]"
    lines: list[str] = []
    prefix = " " * indent
    for item in value:
        rendered = _format_prompt_value(item, indent + 2)
        if isinstance(item, (Mapping, list)) or "\n" in rendered:
            lines.append(f"{prefix}-")
            lines.append(_indent_block(rendered, indent + 2))
            continue
        lines.append(f"{prefix}- {rendered}")
    return "\n".join(lines)


def _format_prompt_value(value: Any, indent: int) -> str:
    if isinstance(value, Mapping):
        return _format_mapping(value, indent)
    if isinstance(value, list):
        return _format_sequence(value, indent)
    if isinstance(value, str):
        return value
    return _stringify_scalar(value)


def _render_character_settings(value: Any) -> str:
    if not isinstance(value, Mapping):
        return _format_prompt_value(value, 0)
    lines: list[str] = []
    description = str(value.get("description") or "").strip()
    if description:
        lines.append(f"角色描述：{description}")
    prompt_summary = str(value.get("prompt_summary") or "").strip()
    if prompt_summary:
        lines.append(f"角色摘要：{prompt_summary}")
    personality_prompt = str(value.get("personality_prompt") or "").strip()
    if personality_prompt:
        lines.append("角色补充设定：")
        lines.append(personality_prompt)
    extras = {
        key: item
        for key, item in value.items()
        if key not in {"description", "prompt_summary", "personality_prompt"}
    }
    if extras:
        lines.append("其他角色设定：")
        for key, item in extras.items():
            lines.append(f"- {key}：{_format_prompt_value(item, 0)}")
    return "\n".join(lines) if lines else "未提供额外角色设定。"


def _render_session_state(value: Any) -> str:
    if not isinstance(value, Mapping):
        return _format_prompt_value(value, 0)
    lines: list[str] = []
    relation_score = value.get("relation_score")
    if relation_score not in (None, ""):
        lines.append(f"当前关系分为 {relation_score}。")
    persona = value.get("persona")
    if isinstance(persona, Mapping) and persona:
        persona_parts = [
            f"{key} 为“{_stringify_scalar(item)}”"
            for key, item in persona.items()
            if item not in (None, "", [], {})
        ]
        if persona_parts:
            lines.append("当前人格状态中，" + "，".join(persona_parts) + "。")
    elif isinstance(persona, str) and persona.strip():
        lines.append(f"当前人格状态：{persona.strip()}")
    active_tags = value.get("active_tags")
    if isinstance(active_tags, list):
        tag_names = [str(item).strip() for item in active_tags if str(item).strip()]
        lines.append("当前激活标签：" + ("、".join(tag_names) if tag_names else "无") + "。")
    return "\n".join(lines) if lines else "当前没有额外会话状态。"


def _render_tag_catalog(value: Any) -> str:
    if not isinstance(value, list):
        return _format_prompt_value(value, 0)
    if not value:
        return "当前没有可引用的标签目录。"
    lines = ["当前可引用的标签如下："]
    for item in value:
        if not isinstance(item, Mapping):
            continue
        index = item.get("index")
        tag_id = str(item.get("tag_id") or "").strip() or "unknown"
        brief = str(item.get("brief") or "").strip()
        sentence = f"{index}. {tag_id}" if index not in (None, "") else tag_id
        if brief:
            sentence += f"：{brief}"
        lines.append(sentence)
    return "\n".join(lines)


def _render_visible_messages(value: Any) -> str:
    if not isinstance(value, list):
        return _format_prompt_value(value, 0)
    if not value:
        return "最近没有可见消息。"
    lines: list[str] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, Mapping):
            lines.append(f"{index}. {_format_prompt_value(item, 0)}")
            continue
        role = str(item.get("role") or "unknown").strip()
        speaker = str(item.get("speaker") or "").strip()
        if role == "user":
            prefix = f"{index}. 用户"
            if speaker:
                prefix += f" {speaker}"
        elif role == "assistant" and item.get("is_thought"):
            prefix = f"{index}. 助手内部事件摘要"
        elif role == "assistant":
            prefix = f"{index}. 助手"
        else:
            prefix = f"{index}. {role}"
        content = str(item.get("content") or "").strip() or "（空内容）"
        suffix_parts: list[str] = []
        tags = item.get("tags")
        if isinstance(tags, list):
            tag_names = [str(tag).strip() for tag in tags if str(tag).strip()]
            if tag_names:
                suffix_parts.append("标签：" + "、".join(tag_names))
        if item.get("is_retracted"):
            suffix_parts.append("该消息之后被撤回")
        suffix = f"（{'；'.join(suffix_parts)}）" if suffix_parts else ""
        lines.append(f"{prefix}：{content}{suffix}")
    return "\n".join(lines)


def _render_memory_context(value: Any) -> str:
    if not isinstance(value, list):
        return _format_prompt_value(value, 0)
    if not value:
        return "没有检索到相关长期记忆。"
    lines: list[str] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, Mapping):
            lines.append(f"{index}. {_format_prompt_value(item, 0)}")
            continue
        source = str(item.get("source") or "unknown").strip()
        scope = str(item.get("scope") or "").strip()
        summary = str(item.get("summary") or "").strip()
        content = str(item.get("content") or "").strip()
        header = f"{index}. 来自 {source} 的记忆"
        if scope:
            header += f"（范围：{scope}）"
        details: list[str] = []
        if summary:
            details.append(f"摘要：{summary}")
        if content:
            details.append(f"内容：{content}")
        tags = item.get("tags")
        if isinstance(tags, list):
            tag_names = [str(tag).strip() for tag in tags if str(tag).strip()]
            if tag_names:
                details.append("标签：" + "、".join(tag_names))
        lines.append(header + "。")
        if details:
            lines.append("   " + " ".join(details))
    return "\n".join(lines)


def _render_runtime_event(value: Any) -> str:
    if not isinstance(value, Mapping):
        return _format_prompt_value(value, 0)
    lines: list[str] = []
    event_type = str(value.get("event_type") or "unknown").strip()
    target_type = str(value.get("target_type") or "unknown").strip()
    lines.append(f"当前事件类型为 {event_type}，目标类型为 {target_type}。")
    if sender := str(value.get("external_sender_display_name") or "").strip():
        lines.append(f"当前外部发送者显示名为 {sender}。")
    if count := value.get("aggregated_message_count"):
        lines.append(f"本轮聚合了 {count} 条消息。")
    if retry_attempt := value.get("chat_retry_attempt"):
        lines.append(f"当前是第 {retry_attempt} 次处理尝试。")
    if im_kind := str(value.get("im_message_kind") or "").strip():
        lines.append(f"IM 消息类型为 {im_kind}。")
    im_context = value.get("im_context")
    if isinstance(im_context, Mapping) and im_context:
        details = [
            f"{key}={_stringify_scalar(item)}"
            for key, item in im_context.items()
            if item not in (None, "", [], {})
        ]
        if details:
            lines.append("IM 上下文：" + "，".join(details) + "。")
    route_context = value.get("im_route_context")
    if isinstance(route_context, Mapping) and route_context:
        details = [
            f"{key}={_stringify_scalar(item)}"
            for key, item in route_context.items()
            if item not in (None, "", [], {})
        ]
        if details:
            lines.append("路由上下文：" + "，".join(details) + "。")
    for key, item in value.items():
        if key in {
            "event_type",
            "target_type",
            "external_sender_display_name",
            "aggregated_message_count",
            "chat_retry_attempt",
            "im_message_kind",
            "im_context",
            "im_route_context",
        }:
            continue
        if item in (None, "", [], {}):
            continue
        lines.append(f"{key}：{_format_prompt_value(item, 0)}")
    return "\n".join(lines)


def _render_pending_wakeups(value: Any) -> str:
    if not isinstance(value, list):
        return _format_prompt_value(value, 0)
    if not value:
        return "当前没有待执行的唤醒任务。"
    lines = ["当前待执行的唤醒任务："]
    for index, item in enumerate(value, start=1):
        if not isinstance(item, Mapping):
            lines.append(f"{index}. {_format_prompt_value(item, 0)}")
            continue
        task_id = str(item.get("id") or "unknown").strip()
        run_at = str(item.get("run_at") or "unknown").strip()
        reason = str(item.get("reason") or "未提供原因").strip()
        status = str(item.get("status") or "unknown").strip()
        lines.append(f"{index}. 任务 {task_id} 将在 {run_at} 执行，状态为 {status}，原因：{reason}。")
    return "\n".join(lines)


def _render_merge_context(value: Any) -> str:
    if value in (None, "", [], {}):
        return "当前没有合并上下文。"
    if not isinstance(value, Mapping):
        return _format_prompt_value(value, 0)
    lines: list[str] = []
    source_state = value.get("source_state")
    if isinstance(source_state, Mapping):
        lines.append("来源会话状态如下：")
        lines.append(_render_session_state(source_state))
    for key, item in value.items():
        if key == "source_state" or item in (None, "", [], {}):
            continue
        lines.append(f"{key}：{_format_prompt_value(item, 0)}")
    return "\n".join(lines) if lines else "当前没有合并上下文。"


def _render_provider_capabilities(value: Any) -> str:
    if not isinstance(value, Mapping):
        return _format_prompt_value(value, 0)
    if not value:
        return "当前没有额外的模型能力提示。"
    lines = ["当前模型能力提示："]
    for key, item in value.items():
        if item in (None, "", [], {}):
            continue
        lines.append(f"- {key}：{_format_prompt_value(item, 0)}")
    return "\n".join(lines)


def _render_wakeup_context(value: Any) -> str:
    if value in (None, "", [], {}):
        return "当前没有唤醒上下文。"
    return _format_prompt_value(value, 0)


def _render_prompt_variable(variable_name: str, value: Any) -> str:
    renderers = {
        "character_settings": _render_character_settings,
        "session_state": _render_session_state,
        "tag_catalog": _render_tag_catalog,
        "visible_messages": _render_visible_messages,
        "memory_context": _render_memory_context,
        "runtime_event": _render_runtime_event,
        "pending_wakeups": _render_pending_wakeups,
        "merge_context": _render_merge_context,
        "provider_capabilities": _render_provider_capabilities,
        "wakeup_context": _render_wakeup_context,
    }
    renderer = renderers.get(variable_name)
    if renderer is not None:
        return renderer(value)
    return _format_prompt_value(value, 0)


def coerce_render_value(value: Any, *, variable_name: str | None = None) -> str:
    if isinstance(value, str):
        return value
    if variable_name:
        return _render_prompt_variable(variable_name, value)
    return _format_prompt_value(value, 0)


def render_template(content: str, variables: dict[str, Any]) -> str:
    sanitized = sanitize_snapshot(variables)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in sanitized:
            raise KeyError(key)
        return coerce_render_value(sanitized[key], variable_name=key)

    return PLACEHOLDER_RE.sub(replace, content)
