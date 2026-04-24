from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from .config import PLUGIN_PLATFORM, utc_now_iso


class BridgePayloadMixin:
    def _normalize_onebot_event(
        self,
        bot: Any,
        event: Any,
        private_event_type: Any,
        group_event_type: Any,
    ) -> dict[str, Any] | None:
        sender_user_id = str(getattr(event, "user_id", "") or "")
        if sender_user_id and sender_user_id == str(getattr(bot, "self_id", "") or ""):
            return None
        text = ""
        if hasattr(event, "get_plaintext"):
            text = str(event.get_plaintext() or "").strip()
        if not text:
            return None
        occurred_at = self._event_occurred_at(event)
        raw_payload = self._compact_onebot_payload(self._dump_onebot_payload(event))
        sender = getattr(event, "sender", None)
        sender_display_name = None
        if sender is not None:
            sender_display_name = (
                str(
                    getattr(sender, "card", None)
                    or getattr(sender, "nickname", None)
                    or ""
                ).strip()
                or None
            )
        base_payload = {
            "account_id": str(getattr(bot, "self_id", "") or ""),
            "sender_id": sender_user_id or None,
            "sender_display_name": sender_display_name,
            "text": text,
            "message_id": str(getattr(event, "message_id", "") or ""),
            "occurred_at": occurred_at,
            "raw_payload": raw_payload,
        }
        if isinstance(event, private_event_type):
            return {
                **base_payload,
                "message_kind": "private",
                "conversation_id": sender_user_id,
                "metadata_json": {
                    "platform": PLUGIN_PLATFORM,
                    "conversation_kind": "private",
                    "bot_self_id": str(getattr(bot, "self_id", "") or ""),
                },
            }
        if isinstance(event, group_event_type):
            group_id = str(getattr(event, "group_id", "") or "").strip()
            if not group_id:
                return None
            return {
                **base_payload,
                "message_kind": "group",
                "conversation_id": group_id,
                "group_name": None,
                "metadata_json": {
                    "platform": PLUGIN_PLATFORM,
                    "conversation_kind": "group",
                    "bot_self_id": str(getattr(bot, "self_id", "") or ""),
                    "group_id": group_id,
                },
            }
        return None

    def _event_occurred_at(self, event: Any) -> str:
        time_value = getattr(event, "time", None)
        if isinstance(time_value, datetime):
            if time_value.tzinfo:
                return time_value.astimezone(UTC).isoformat()
            return time_value.replace(tzinfo=UTC).isoformat()
        if isinstance(time_value, (int, float)):
            return datetime.fromtimestamp(float(time_value), tz=UTC).isoformat()
        return utc_now_iso()

    def _dump_onebot_payload(self, value: Any) -> dict[str, Any]:
        for method_name in ("model_dump", "dict"):
            method = getattr(value, method_name, None)
            if callable(method):
                try:
                    dumped = method()
                except TypeError:
                    dumped = method(exclude_none=False)
                if isinstance(dumped, dict):
                    return dumped
        return {}

    def _compact_onebot_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        compact: dict[str, Any] = {}
        for key in (
            "post_type",
            "message_type",
            "sub_type",
            "message_format",
            "raw_message",
            "message_seq",
            "real_seq",
            "time",
            "to_me",
            "font",
        ):
            value = payload.get(key)
            if value not in (None, "", [], {}):
                compact[key] = value
        for key in ("message", "original_message"):
            segments = self._compact_onebot_segments(payload.get(key))
            if segments:
                compact[key] = segments
        sender = payload.get("sender")
        if isinstance(sender, dict):
            sender_summary = {
                field: str(sender.get(field)).strip()
                for field in ("nickname", "card", "user_id")
                if str(sender.get(field) or "").strip()
            }
            if sender_summary:
                compact["sender"] = sender_summary
        raw_summary = self._compact_onebot_raw_envelope(payload.get("raw"))
        if raw_summary:
            compact["raw"] = raw_summary
        return compact

    def _compact_onebot_segments(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        segments: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            segment_type = str(item.get("type") or "").strip()
            data = item.get("data")
            compact_data: dict[str, Any] = {}
            if isinstance(data, dict):
                for key in ("text", "qq", "id", "file", "url", "name"):
                    current = data.get(key)
                    if current not in (None, "", [], {}):
                        compact_data[key] = current
            if not segment_type and not compact_data:
                continue
            segment_payload: dict[str, Any] = {}
            if segment_type:
                segment_payload["type"] = segment_type
            if compact_data:
                segment_payload["data"] = compact_data
            segments.append(segment_payload)
        return segments

    def _compact_onebot_raw_envelope(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        compact = {
            key: value[key]
            for key in (
                "chatType",
                "msgId",
                "msgSeq",
                "msgTime",
                "msgType",
                "peerUid",
                "peerUin",
                "senderUid",
                "senderUin",
                "subMsgType",
            )
            if value.get(key) not in (None, "", [], {})
        }
        text_fragments: list[str] = []
        for element in value.get("elements") or []:
            if not isinstance(element, dict):
                continue
            text_element = element.get("textElement")
            if not isinstance(text_element, dict):
                continue
            content = str(text_element.get("content") or "").strip()
            if content:
                text_fragments.append(content)
        if text_fragments:
            compact["text_fragments"] = text_fragments
        return compact

    def _apply_nonebot_env(self) -> None:
        os.environ["DRIVER"] = self.config["driver"]
        os.environ["ONEBOT_WS_URLS"] = json.dumps(
            self.config["onebot_ws_urls"], ensure_ascii=False
        )
        os.environ["ONEBOT_ACCESS_TOKEN"] = self.config["onebot_access_token"]
        os.environ["COMMAND_START"] = json.dumps(
            self.config["command_start"], ensure_ascii=False
        )
        os.environ["COMMAND_SEP"] = json.dumps(
            self.config["command_sep"], ensure_ascii=False
        )
        os.environ["HOST"] = "127.0.0.1"
        os.environ["PORT"] = "8080"
