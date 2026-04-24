from __future__ import annotations

from pathlib import Path
import json
import threading
from typing import Any

from .config import utc_now_iso


class RouteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._payload = self._load()

    def _default_payload(self) -> dict[str, Any]:
        return {
            "bindings": {
                "private": {},
                "group": {},
            },
            "targets": {},
            "platform_bindings": {},
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default_payload()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return self._default_payload()
        if not isinstance(payload, dict):
            return self._default_payload()
        if "bindings" in payload:
            return {
                "bindings": {
                    "private": dict((payload.get("bindings") or {}).get("private") or {}),
                    "group": dict((payload.get("bindings") or {}).get("group") or {}),
                },
                "targets": dict(payload.get("targets") or {}),
                "platform_bindings": dict(payload.get("platform_bindings") or {}),
            }
        migrated = self._default_payload()
        for message_kind in ("private", "group"):
            bucket = payload.get(message_kind)
            if not isinstance(bucket, dict):
                continue
            for key, value in bucket.items():
                if not isinstance(value, dict):
                    continue
                if "target_type" not in value or "target_id" not in value:
                    continue
                route = {
                    "target_type": str(value.get("target_type") or "").strip(),
                    "target_id": str(value.get("target_id") or "").strip(),
                    "metadata_json": dict(value.get("metadata_json") or {}),
                }
                migrated["bindings"][message_kind][key] = {
                    "attached": True,
                    "route": route,
                    "tags": list(route["metadata_json"].get("tags") or []),
                    "updated_at": utc_now_iso(),
                }
                target_id = route["target_id"]
                if target_id:
                    migrated["targets"][target_id] = {
                        "target_type": route["target_type"],
                        "target_id": target_id,
                        "name": target_id,
                        "created_at": utc_now_iso(),
                        "updated_at": utc_now_iso(),
                        "tags": list(route["metadata_json"].get("tags") or []),
                    }
        return migrated

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(self._payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def _binding_key(self, account_id: str, conversation_id: str) -> str:
        return f"{account_id}:{conversation_id}"

    def get_binding(self, message_kind: str, account_id: str, conversation_id: str) -> dict[str, Any] | None:
        key = self._binding_key(account_id, conversation_id)
        with self._lock:
            payload = dict(((self._payload.get("bindings") or {}).get(message_kind) or {}).get(key) or {})
        return payload or None

    def save_binding(
        self,
        message_kind: str,
        account_id: str,
        conversation_id: str,
        *,
        route: dict[str, Any] | None,
        attached: bool,
        tags: list[str],
    ) -> dict[str, Any]:
        key = self._binding_key(account_id, conversation_id)
        binding = {
            "attached": bool(attached),
            "route": dict(route or {}) if route else None,
            "tags": list(tags),
            "updated_at": utc_now_iso(),
        }
        with self._lock:
            bucket = self._payload.setdefault("bindings", {}).setdefault(message_kind, {})
            bucket[key] = binding
            self._save()
        return dict(binding)

    def update_binding_tags(
        self,
        message_kind: str,
        account_id: str,
        conversation_id: str,
        tags: list[str],
    ) -> dict[str, Any] | None:
        key = self._binding_key(account_id, conversation_id)
        with self._lock:
            bucket = self._payload.setdefault("bindings", {}).setdefault(message_kind, {})
            current = dict(bucket.get(key) or {})
            if not current:
                return None
            current["tags"] = list(tags)
            current["updated_at"] = utc_now_iso()
            route = dict(current.get("route") or {})
            if route:
                metadata_json = dict(route.get("metadata_json") or {})
                metadata_json["tags"] = list(tags)
                route["metadata_json"] = metadata_json
                current["route"] = route
            bucket[key] = current
            self._save()
        return current

    def upsert_target(
        self,
        *,
        target_type: str,
        target_id: str,
        name: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self._lock:
            bucket = self._payload.setdefault("targets", {})
            current = dict(bucket.get(target_id) or {})
            target = {
                "target_type": target_type,
                "target_id": target_id,
                "name": name or current.get("name") or target_id,
                "created_at": current.get("created_at") or now,
                "updated_at": now,
                "tags": list(tags if tags is not None else current.get("tags") or []),
            }
            bucket[target_id] = target
            self._save()
        return target

    def get_target(self, target_id: str) -> dict[str, Any] | None:
        with self._lock:
            payload = dict((self._payload.get("targets") or {}).get(target_id) or {})
        return payload or None

    def list_targets(self) -> list[dict[str, Any]]:
        with self._lock:
            items = [dict(item) for item in (self._payload.get("targets") or {}).values()]
        items.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return items

    def list_bindings(self, message_kind: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            bindings = dict(self._payload.get("bindings") or {})
        items: list[dict[str, Any]] = []
        kinds = [message_kind] if message_kind else ["private", "group"]
        for kind in kinds:
            if kind not in {"private", "group"}:
                continue
            bucket = dict(bindings.get(kind) or {})
            for key, value in bucket.items():
                account_id, conversation_id = key.split(":", 1) if ":" in key else (key, "")
                items.append(
                    {
                        "message_kind": kind,
                        "account_id": account_id,
                        "conversation_id": conversation_id,
                        "binding": dict(value or {}),
                    }
                )
        items.sort(key=lambda item: str((item.get("binding") or {}).get("updated_at") or ""), reverse=True)
        return items

    def get_platform_binding(self, account_id: str, conversation_id: str) -> dict[str, Any] | None:
        key = self._binding_key(account_id, conversation_id)
        with self._lock:
            payload = dict((self._payload.get("platform_bindings") or {}).get(key) or {})
        return payload or None

    def save_platform_binding(
        self,
        account_id: str,
        conversation_id: str,
        *,
        platform_user_id: str,
        platform_username: str,
    ) -> dict[str, Any]:
        key = self._binding_key(account_id, conversation_id)
        binding = {
            "platform_user_id": platform_user_id,
            "platform_username": platform_username,
            "updated_at": utc_now_iso(),
        }
        with self._lock:
            bucket = self._payload.setdefault("platform_bindings", {})
            bucket[key] = binding
            self._save()
        return dict(binding)

    def clear_platform_binding(self, account_id: str, conversation_id: str) -> None:
        key = self._binding_key(account_id, conversation_id)
        with self._lock:
            bucket = self._payload.setdefault("platform_bindings", {})
            bucket.pop(key, None)
            self._save()
