from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

ImRouteHandler = Callable[
    [Any],
    "ImInboundRoute | dict[str, Any] | None | Awaitable[ImInboundRoute | dict[str, Any] | None]",
]
ImReplyHandler = Callable[
    [Any],
    (
        "ImDeliveryResult | dict[str, Any] | bool | None | "
        "Awaitable[ImDeliveryResult | dict[str, Any] | bool | None]"
    ),
]
LifecycleHandler = Callable[[], "None | Awaitable[None]"]


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class ImInboundRoute:
    target_type: str
    target_id: str
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImPrivateMessage:
    account_id: str
    conversation_id: str
    sender_id: str | None
    sender_display_name: str | None
    text: str
    message_id: str
    occurred_at: str
    sender_user_id: str | None = None
    owner_user_id: str | None = None
    memory_owner_user_id: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImGroupMessage:
    account_id: str
    conversation_id: str
    sender_id: str | None
    sender_display_name: str | None
    text: str
    message_id: str
    occurred_at: str
    group_name: str | None = None
    sender_user_id: str | None = None
    owner_user_id: str | None = None
    memory_owner_user_id: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImOutboundReply:
    delivery_id: str
    plugin_id: str
    action_id: str | None
    message_id: str | None
    target_type: str
    target_id: str
    reply_text: str
    source_message_id: str | None
    external_account_id: str | None
    external_conversation_id: str | None
    external_message_id: str | None
    external_sender_id: str | None
    external_sender_display_name: str | None
    metadata_json: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None


@dataclass
class ImDeliveryResult:
    ok: bool
    error: str | None = None
    retryable: bool = True
    metadata_json: dict[str, Any] = field(default_factory=dict)
