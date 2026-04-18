from __future__ import annotations

from typing import Any

import orjson


class ChatDispatchCodec:
    """Serializes queue payloads for transport backends."""

    def encode_payload(self, payload: dict[str, Any]) -> str:
        return orjson.dumps(payload).decode("utf-8")

    def decode_payload(self, raw_payload: str | bytes | None) -> dict[str, Any]:
        if not raw_payload:
            return {}
        if isinstance(raw_payload, bytes):
            raw_payload = raw_payload.decode("utf-8")
        decoded = orjson.loads(raw_payload)
        return decoded if isinstance(decoded, dict) else {}
