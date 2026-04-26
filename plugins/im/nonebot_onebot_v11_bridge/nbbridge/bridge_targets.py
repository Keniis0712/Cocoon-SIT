from __future__ import annotations

from typing import Any

from .config import PLUGIN_PLATFORM


class BridgeTargetMixin:
    def _resolve_create_type_and_args(
        self, args: list[str]
    ) -> tuple[str, list[str], str | None]:
        if not args:
            return "", [], "Usage: /create <cocoon|group> [name] [character_name]"
        first = str(args[0]).strip().lower()
        if first == "cocoon":
            return "cocoon", args[1:], None
        if first in {"chat_group", "group"}:
            return "chat_group", args[1:], None
        return "", [], "Usage: /create <cocoon|group> [name] [character_name]"

    async def _resolve_create_character_and_name(
        self, payload: dict[str, Any], *, args: list[str]
    ) -> tuple[str, str, str | None]:
        characters = await self._fetch_accessible_characters(payload)
        if not characters:
            return "", "", "No accessible characters. Use /list characters first."
        explicit_ref = self._extract_explicit_character_ref(args, characters)
        name_parts = args[:-1] if explicit_ref is not None else args
        name = " ".join(name_parts).strip()
        if explicit_ref is not None:
            match = self._match_accessible_character(characters, explicit_ref)
            if match is None:
                return "", name, f"Character not found: {explicit_ref}"
            return str(match["character_id"]), name, None
        if len(characters) == 1:
            return str(characters[0]["character_id"]), name, None
        return (
            "",
            name,
            "Multiple characters are available. Use /list characters and provide the character name.",
        )

    def _extract_explicit_character_ref(
        self, args: list[str], characters: list[dict[str, Any]]
    ) -> str | None:
        if not args:
            return None
        candidate = str(args[-1]).strip()
        if not candidate:
            return None
        if self._match_accessible_character(characters, candidate) is not None:
            return candidate
        return None

    def _match_accessible_character(
        self, characters: list[dict[str, Any]], ref: str
    ) -> dict[str, Any] | None:
        normalized = str(ref).strip()
        if not normalized:
            return None
        matches = [
            item
            for item in characters
            if str(item.get("name") or "").strip().casefold() == normalized.casefold()
        ]
        if len(matches) == 1:
            return matches[0]
        return None

    def _parse_list_request(self, args: list[str]) -> tuple[str, int, str | None]:
        if not args:
            return "cocoons", 1, None
        normalized = str(args[0]).strip().lower()
        kind_aliases = {
            "cocoon": "cocoons",
            "cocoons": "cocoons",
            "target": "targets",
            "targets": "targets",
            "character": "characters",
            "characters": "characters",
            "char": "characters",
            "chars": "characters",
        }
        if normalized.isdigit():
            page = max(int(normalized), 1)
            return "cocoons", page, None
        list_kind = kind_aliases.get(normalized)
        if list_kind is None:
            return "", 1, "Usage: /list [cocoons|targets|characters] [page]"
        if len(args) < 2:
            return list_kind, 1, None
        page_raw = str(args[1]).strip()
        if not page_raw.isdigit():
            return "", 1, "Page must be a positive integer."
        return list_kind, max(int(page_raw), 1), None

    def _render_target_page(
        self,
        payload: dict[str, Any],
        items: list[dict[str, Any]],
        page: int,
        *,
        list_kind: str,
        fetch_error: str,
    ) -> str:
        heading_label = "cocoons" if list_kind == "cocoons" else "targets"
        if not items and fetch_error:
            return f"Failed to fetch {heading_label}: {fetch_error}"
        if not items:
            return f"No {heading_label} available."
        binding = self.route_store.get_binding(
            "private",
            str(payload["account_id"]),
            str(payload["conversation_id"]),
        )
        current_target_id = str(((binding or {}).get("route") or {}).get("target_id") or "")
        page_items, current_page, total_pages = self._paginate_items(items, page)
        lines = [f"{heading_label} page {current_page}/{total_pages}, total {len(items)}"]
        if fetch_error:
            lines.append(f"Using cached targets because fetch failed: {fetch_error}")
        for index, item in enumerate(
            page_items, start=(current_page - 1) * self.LIST_PAGE_SIZE + 1
        ):
            marker = (
                "*"
                if item["target_id"] == current_target_id and (binding or {}).get("attached")
                else "-"
            )
            tags = ", ".join(item.get("tags") or [])
            suffix = f" tags=[{tags}]" if tags else ""
            item_label = self._target_display_label(item, list_kind=list_kind)
            lines.append(f"{index}. {marker} {item_label}{suffix}".strip())
        if total_pages > 1:
            lines.append(
                f"Use /list {heading_label} {min(current_page + 1, total_pages)} to view more."
            )
        return "\n".join(lines)

    def _render_character_page(self, items: list[dict[str, Any]], page: int) -> str:
        if not items:
            return "No accessible characters."
        page_items, current_page, total_pages = self._paginate_items(items, page)
        lines = [f"characters page {current_page}/{total_pages}, total {len(items)}"]
        for index, item in enumerate(
            page_items, start=(current_page - 1) * self.LIST_PAGE_SIZE + 1
        ):
            name = str(item.get("name") or "").strip() or "unnamed character"
            lines.append(f"{index}. - {name}")
        if total_pages > 1:
            lines.append(
                f"Use /list characters {min(current_page + 1, total_pages)} to view more."
            )
        return "\n".join(lines)

    def _paginate_items(
        self, items: list[dict[str, Any]], page: int
    ) -> tuple[list[dict[str, Any]], int, int]:
        total_pages = max((len(items) + self.LIST_PAGE_SIZE - 1) // self.LIST_PAGE_SIZE, 1)
        current_page = min(max(page, 1), total_pages)
        start = (current_page - 1) * self.LIST_PAGE_SIZE
        end = start + self.LIST_PAGE_SIZE
        return items[start:end], current_page, total_pages

    def _target_display_label(self, item: dict[str, Any], *, list_kind: str) -> str:
        name = str(item.get("name") or "").strip()
        target_type = str(item.get("target_type") or "").strip()
        if list_kind == "cocoons":
            return name or "unnamed cocoon"
        prefix = target_type or "target"
        if name:
            return f"{prefix} {name}"
        return prefix

    def _parse_attach_args(self, args: list[str]) -> tuple[str, str, str | None]:
        if len(args) < 2:
            return "", "", "Usage: /attach <id|name> <value>"
        mode = str(args[0]).strip().lower()
        value = " ".join(str(item).strip() for item in args[1:] if str(item).strip()).strip()
        if mode not in {"id", "name"} or not value:
            return "", "", "Usage: /attach <id|name> <value>"
        return mode, value, None

    async def _resolve_attach_target(
        self,
        payload: dict[str, Any],
        mode: str,
        value: str,
        allowed_types: set[str],
    ) -> tuple[dict[str, Any] | None, str | None]:
        candidates = await self._list_attach_candidates(payload, allowed_types)
        if mode == "id":
            exact_matches = [
                item for item in candidates if str(item.get("target_id") or "").strip() == value
            ]
        else:
            exact_matches = [
                item
                for item in candidates
                if str(item.get("name") or "").strip().casefold() == value.casefold()
            ]
        if len(exact_matches) == 1:
            return exact_matches[0], None
        if len(exact_matches) > 1:
            if mode == "name":
                return None, "Multiple targets share that name. Use /attach id <id>."
            return None, "Multiple targets share that id. Check /list targets."
        return None, None

    async def _resolve_target_by_id(
        self,
        payload: dict[str, Any],
        target_id: str,
        *,
        allowed_types: set[str],
    ) -> tuple[dict[str, Any] | None, str | None]:
        candidates = await self._list_attach_candidates(payload, allowed_types)
        for item in candidates:
            if str(item.get("target_id") or "").strip() == str(target_id).strip():
                return item, None
        return None, None

    async def _list_attach_candidates(
        self, payload: dict[str, Any], allowed_types: set[str]
    ) -> list[dict[str, Any]]:
        try:
            items = await self._fetch_accessible_targets(payload)
        except Exception:  # noqa: BLE001
            items = self.route_store.list_targets()
        filtered = [
            item
            for item in items
            if str(item.get("target_type") or "") in allowed_types
        ]
        filtered.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return filtered

    def _build_route(
        self,
        *,
        target_type: str,
        target_id: str,
        message_kind: str,
        account_id: str,
        conversation_id: str,
        tags: list[str],
    ) -> dict[str, Any]:
        return {
            "target_type": target_type,
            "target_id": target_id,
            "metadata_json": {
                "platform": PLUGIN_PLATFORM,
                "conversation_kind": message_kind,
                "external_account_id": account_id,
                "external_conversation_id": conversation_id,
                "tags": list(tags),
            },
        }

    async def _sync_attached_routes(self) -> None:
        for item in self.route_store.list_bindings("private"):
            binding = dict(item.get("binding") or {})
            if not binding.get("attached") or not binding.get("route"):
                continue
            try:
                await self._upsert_backend_route(dict(binding.get("route") or {}))
            except Exception as exc:  # noqa: BLE001
                self.ctx.report_runtime_error(f"Failed to sync private route: {exc}")
        for item in self.route_store.list_group_states():
            group_state = dict(item.get("group_state") or {})
            if not group_state.get("enabled") or not group_state.get("attached") or not group_state.get("route"):
                continue
            try:
                await self._upsert_backend_route(dict(group_state.get("route") or {}))
            except Exception as exc:  # noqa: BLE001
                self.ctx.report_runtime_error(f"Failed to sync group route: {exc}")

    async def _upsert_backend_route(self, route: dict[str, Any]) -> None:
        metadata_json = dict(route.get("metadata_json") or {})
        await self.ctx.upsert_im_target_route(
            target_type=str(route.get("target_type") or "").strip(),
            target_id=str(route.get("target_id") or "").strip(),
            external_platform=str(metadata_json.get("platform") or "").strip(),
            conversation_kind=str(metadata_json.get("conversation_kind") or "").strip(),
            external_account_id=str(metadata_json.get("external_account_id") or "").strip(),
            external_conversation_id=str(
                metadata_json.get("external_conversation_id") or ""
            ).strip(),
            metadata_json=metadata_json,
        )

    async def _delete_backend_route(
        self, *, message_kind: str, account_id: str, conversation_id: str
    ) -> None:
        await self.ctx.delete_im_target_route(
            external_platform=PLUGIN_PLATFORM,
            conversation_kind=message_kind,
            external_account_id=account_id,
            external_conversation_id=conversation_id,
        )

    def _private_cocoon_name_from_payload(self, payload: dict[str, Any]) -> str:
        display_name = str(
            payload.get("sender_display_name")
            or payload.get("sender_id")
            or payload.get("conversation_id")
            or ""
        ).strip()
        return f"{self.config['private_cocoon_name_prefix']} {display_name}".strip()

    async def _fetch_accessible_targets(
        self, payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        response = await self.ctx.list_accessible_targets(**self._owner_lookup_identity(payload))
        items = []
        for raw_item in list(response.get("items") or []):
            target_type = str(raw_item.get("target_type") or "").strip()
            target_id = str(raw_item.get("target_id") or "").strip()
            if target_type not in {"cocoon", "chat_group"} or not target_id:
                continue
            local_target = self.route_store.get_target(target_id) or {}
            name = str(raw_item.get("name") or local_target.get("name") or target_id).strip() or target_id
            self.route_store.upsert_target(
                target_type=target_type,
                target_id=target_id,
                name=name,
            )
            items.append(
                {
                    "target_type": target_type,
                    "target_id": target_id,
                    "name": name,
                    "tags": list(local_target.get("tags") or []),
                    "created_at": str(raw_item.get("created_at") or ""),
                }
            )
        items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return items

    async def _fetch_accessible_characters(
        self, payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        response = await self.ctx.list_accessible_characters(**self._owner_lookup_identity(payload))
        items = []
        for raw_item in list(response.get("items") or []):
            character_id = str(raw_item.get("character_id") or "").strip()
            if not character_id:
                continue
            items.append(
                {
                    "character_id": character_id,
                    "name": str(raw_item.get("name") or character_id).strip() or character_id,
                    "created_at": str(raw_item.get("created_at") or ""),
                }
            )
        items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return items

    def _group_room_name_from_payload(self, payload: dict[str, Any]) -> str:
        group_name = str(payload.get("group_name") or payload.get("conversation_id") or "").strip()
        return f"{self.config['group_room_name_prefix']} {group_name}".strip()
