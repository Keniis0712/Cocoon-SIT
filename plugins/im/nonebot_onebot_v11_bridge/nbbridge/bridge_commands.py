from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import PLUGIN_PLATFORM


@dataclass(frozen=True)
class CommandSpec:
    path: tuple[str, ...]
    usage: str
    summary: str
    help_text: str
    op_only: bool
    handler_name: str


class BridgeCommandMixin:
    def _is_command(self, text: str) -> bool:
        return self._parse_command(text) is not None

    def _parse_command(self, text: str) -> dict[str, Any] | None:
        stripped = text.strip()
        if not stripped:
            return None
        prefix = next(
            (
                item
                for item in self.config["command_start"]
                if stripped.startswith(item)
            ),
            None,
        )
        if prefix is None:
            return None
        body = stripped[len(prefix) :].strip()
        if not body:
            return None
        parts = [str(item).strip() for item in body.split() if str(item).strip()]
        if not parts:
            return None
        return {
            "tokens": [item.lower() for item in parts],
            "raw_tokens": parts,
        }

    def _command_specs(self) -> list[CommandSpec]:
        return [
            CommandSpec(
                path=("help",),
                usage="/help",
                summary="Show available commands.",
                help_text="Use /help, /command help, or /command subcmd help.",
                op_only=False,
                handler_name="_command_help_entry",
            ),
            CommandSpec(
                path=("status",),
                usage="/status",
                summary="Show current private-chat bridge status.",
                help_text="Shows private binding status, account info, and whether you have OP access.",
                op_only=False,
                handler_name="_command_status",
            ),
            CommandSpec(
                path=("bind",),
                usage="/bind <username> <token>",
                summary="Bind this private IM user to a Cocoon user.",
                help_text="Private chat only. Stores the validated Cocoon user binding for this IM account.",
                op_only=False,
                handler_name="_command_bind",
            ),
            CommandSpec(
                path=("unbind",),
                usage="/unbind",
                summary="Remove the stored private IM binding.",
                help_text="Private chat only. Clears the saved Cocoon user binding for this IM account.",
                op_only=False,
                handler_name="_command_unbind",
            ),
            CommandSpec(
                path=("list",),
                usage="/list [cocoons|targets|characters] [page]",
                summary="List accessible cocoons, targets, or characters.",
                help_text="Targets include both cocoons and chat groups. Characters are used with /create.",
                op_only=False,
                handler_name="_command_list",
            ),
            CommandSpec(
                path=("create",),
                usage="/create <cocoon|group> [name] [character_name]",
                summary="Create a cocoon or chat group explicitly.",
                help_text="Use /create cocoon ... for private cocoon creation and /create group ... for chat groups.",
                op_only=False,
                handler_name="_command_create",
            ),
            CommandSpec(
                path=("attach",),
                usage="/attach <id|name> <value>",
                summary="Attach this private chat to a cocoon.",
                help_text="Private chat only. /attach id <cocoon_id> or /attach name <cocoon_name>.",
                op_only=False,
                handler_name="_command_attach",
            ),
            CommandSpec(
                path=("detach",),
                usage="/detach",
                summary="Detach this private chat from its current cocoon.",
                help_text="Private chat only. Removes the active route for this private conversation.",
                op_only=False,
                handler_name="_command_detach",
            ),
            CommandSpec(
                path=("tag",),
                usage="/tag [list|add|remove|clear] ...",
                summary="Manage local route tags for the current private binding.",
                help_text="Tags are stored on the local route and synced into route metadata.",
                op_only=False,
                handler_name="_command_tag",
            ),
            CommandSpec(
                path=("op", "group", "enable"),
                usage="/op group enable <im_group_id>",
                summary="Enable management for an IM group without routing messages yet.",
                help_text="Marks an IM group as enabled. Messages are still ignored until /op group attach is used.",
                op_only=True,
                handler_name="_command_op_group_enable",
            ),
            CommandSpec(
                path=("op", "group", "attach"),
                usage="/op group attach <im_group_id> <chat_group_id>",
                summary="Attach an enabled IM group to a Cocoon chat group.",
                help_text="Creates the backend route so all messages from the IM group are forwarded to the chosen chat_group.",
                op_only=True,
                handler_name="_command_op_group_attach",
            ),
            CommandSpec(
                path=("op", "group", "detach"),
                usage="/op group detach <im_group_id>",
                summary="Detach an enabled IM group from its Cocoon chat group.",
                help_text="Removes the backend route but keeps the IM group enabled for later re-attachment.",
                op_only=True,
                handler_name="_command_op_group_detach",
            ),
            CommandSpec(
                path=("op", "group", "disable"),
                usage="/op group disable <im_group_id>",
                summary="Disable an IM group and remove any active route.",
                help_text="Disables the IM group and clears any current chat_group attachment.",
                op_only=True,
                handler_name="_command_op_group_disable",
            ),
            CommandSpec(
                path=("op", "role", "add"),
                usage="/op role add <im_uid>",
                summary="Grant OP permission to an IM user ID.",
                help_text="Adds an IM UID to the explicit OP allow-list stored in routes.json.",
                op_only=True,
                handler_name="_command_op_role_add",
            ),
            CommandSpec(
                path=("op", "role", "remove"),
                usage="/op role remove <im_uid>",
                summary="Remove explicit OP permission from an IM user ID.",
                help_text="Removes the IM UID from the explicit OP allow-list. The configured im_owner_id always remains OP.",
                op_only=True,
                handler_name="_command_op_role_remove",
            ),
        ]

    async def _handle_command(self, payload: dict[str, Any]) -> str:
        if str(payload.get("message_kind") or "") != "private":
            return ""
        command = self._parse_command(str(payload.get("text") or ""))
        if command is None:
            return ""
        tokens = list(command["tokens"])
        is_op = self._is_op_user(payload)
        if tokens and tokens[0] == "help":
            return self._render_help(tokens[1:], is_op=is_op)
        if tokens and tokens[-1] == "help":
            spec, _ = self._resolve_command(tokens[:-1], is_op=is_op)
            if spec is None:
                return self._unknown_command_response()
            return self._render_command_help(spec)
        spec, args = self._resolve_command(tokens, is_op=is_op)
        if spec is None:
            return self._unknown_command_response()
        handler = getattr(self, spec.handler_name)
        result = handler(payload, args)
        if hasattr(result, "__await__"):
            return await result
        return str(result)

    def _resolve_command(
        self,
        tokens: list[str],
        *,
        is_op: bool,
    ) -> tuple[CommandSpec | None, list[str]]:
        specs = [
            spec
            for spec in self._command_specs()
            if is_op or not spec.op_only
        ]
        for spec in sorted(specs, key=lambda item: len(item.path), reverse=True):
            path = list(spec.path)
            if tokens[: len(path)] == path:
                return spec, tokens[len(path) :]
        return None, []

    def _render_help(self, tokens: list[str], *, is_op: bool) -> str:
        if not tokens:
            specs = [
                spec
                for spec in self._command_specs()
                if spec.path != ("help",) and (is_op or not spec.op_only)
            ]
            lines = ["Available commands:"]
            for spec in specs:
                lines.append(f"- {spec.usage}: {spec.summary}")
            lines.append("Use /command help or /command subcmd help for details.")
            return "\n".join(lines)
        spec, _ = self._resolve_command(tokens, is_op=is_op)
        if spec is None:
            return self._unknown_command_response()
        return self._render_command_help(spec)

    def _render_command_help(self, spec: CommandSpec) -> str:
        return "\n".join(
            [
                f"Usage: {spec.usage}",
                spec.summary,
                spec.help_text,
            ]
        )

    def _unknown_command_response(self) -> str:
        return "Unknown command. Use /help."

    def _command_help_entry(self, payload: dict[str, Any], args: list[str]) -> str:
        return self._render_help(args, is_op=self._is_op_user(payload))

    def _is_op_user(self, payload: dict[str, Any]) -> bool:
        sender_id = str(
            payload.get("sender_id") or payload.get("conversation_id") or ""
        ).strip()
        if not sender_id:
            return False
        if sender_id == str(self.config.get("im_owner_id") or "").strip():
            return True
        return self.route_store.is_explicit_op_user(sender_id)

    def _command_status(self, payload: dict[str, Any], args: list[str]) -> str:
        del args
        message_kind = str(payload["message_kind"])
        account_id = str(payload["account_id"])
        conversation_id = str(payload["conversation_id"])
        binding = self.route_store.get_binding(
            message_kind, account_id, conversation_id
        )
        lines = [
            f"platform: {PLUGIN_PLATFORM}",
            f"conversation_kind: {message_kind}",
            f"account_id: {account_id}",
            f"conversation_id: {conversation_id}",
            f"op_access: {'yes' if self._is_op_user(payload) else 'no'}",
            f"known_targets: {len(self.route_store.list_targets())}",
        ]
        platform_binding = self._platform_binding(payload)
        if platform_binding:
            lines.append(
                "platform_user: "
                f"{platform_binding.get('platform_username') or '-'} "
                f"({platform_binding.get('platform_user_id') or '-'})"
            )
        else:
            lines.append("platform_user: unbound")
        if not binding or not binding.get("route"):
            lines.append("attached: no")
            lines.append("target: none")
            return "\n".join(lines)
        route = dict(binding.get("route") or {})
        target = self.route_store.get_target(str(route.get("target_id") or ""))
        lines.append(f"attached: {'yes' if binding.get('attached') else 'no'}")
        lines.append(f"target_type: {route.get('target_type') or '-'}")
        lines.append(
            "target_name: "
            f"{(target or {}).get('name') or route.get('target_id') or '-'}"
        )
        lines.append(f"tags: {', '.join(binding.get('tags') or []) or '-'}")
        return "\n".join(lines)

    async def _command_bind(self, payload: dict[str, Any], args: list[str]) -> str:
        if len(args) < 2:
            return "Usage: /bind <username> <token>"
        try:
            binding = await self.ctx.verify_user_binding(
                username=str(args[0]), token=str(args[1])
            )
        except Exception as exc:  # noqa: BLE001
            return f"Bind failed: {exc}"
        self.route_store.save_platform_binding(
            str(payload["account_id"]),
            str(payload["conversation_id"]),
            platform_user_id=str(binding.get("user_id") or ""),
            platform_username=str(binding.get("username") or args[0]),
        )
        return f"Bound platform user: {binding.get('username') or args[0]}"

    def _command_unbind(self, payload: dict[str, Any], args: list[str]) -> str:
        del args
        self.route_store.clear_platform_binding(
            str(payload["account_id"]),
            str(payload["conversation_id"]),
        )
        return "Platform binding cleared."

    async def _command_create(self, payload: dict[str, Any], args: list[str]) -> str:
        target_type, create_args, error = self._resolve_create_type_and_args(args)
        if error:
            return error
        owner_identity = self._resolve_owner_identity(payload)
        (
            character_id,
            name,
            character_error,
        ) = await self._resolve_create_character_and_name(
            payload,
            args=create_args,
        )
        if character_error:
            return character_error
        if target_type == "cocoon":
            if not name:
                name = self._private_cocoon_name_from_payload(payload)
            cocoon = await self.ctx.create_cocoon(
                name=name,
                **owner_identity,
                character_id=character_id,
                selected_model_id=self.config["default_model_id"],
            )
            target = self.route_store.upsert_target(
                target_type="cocoon",
                target_id=str(cocoon["id"]),
                name=str(cocoon.get("name") or name),
            )
            return f"Created cocoon: {target['name']}"
        if not name:
            name = self._group_room_name_from_payload(payload)
        room = await self.ctx.create_chat_group(
            name=name,
            **owner_identity,
            character_id=character_id,
            selected_model_id=self.config["default_model_id"],
        )
        target = self.route_store.upsert_target(
            target_type="chat_group",
            target_id=str(room["id"]),
            name=str(room.get("name") or name),
        )
        return f"Created chat_group: {target['name']}"

    async def _command_list(self, payload: dict[str, Any], args: list[str]) -> str:
        list_kind, page, error = self._parse_list_request(args)
        if error:
            return error
        if list_kind == "characters":
            try:
                characters = await self._fetch_accessible_characters(payload)
            except Exception as exc:  # noqa: BLE001
                return f"Failed to fetch characters: {exc}"
            return self._render_character_page(characters, page)
        fetch_error = ""
        try:
            targets = await self._fetch_accessible_targets(payload)
        except Exception as exc:  # noqa: BLE001
            fetch_error = str(exc).strip() or "unknown error"
            targets = self.route_store.list_targets()
        items = (
            [item for item in targets if item.get("target_type") == "cocoon"]
            if list_kind == "cocoons"
            else targets
        )
        return self._render_target_page(
            payload, items, page, list_kind=list_kind, fetch_error=fetch_error
        )

    async def _command_attach(self, payload: dict[str, Any], args: list[str]) -> str:
        account_id = str(payload["account_id"])
        conversation_id = str(payload["conversation_id"])
        existing = self.route_store.get_binding("private", account_id, conversation_id)
        attach_mode, attach_value, error = self._parse_attach_args(args)
        if error:
            return error
        target, error = await self._resolve_attach_target(
            payload,
            attach_mode,
            attach_value,
            {"cocoon"},
        )
        if error:
            return error
        if target is None:
            return "Target not found. Use /list and then /attach id <id>."
        tags = list((existing or {}).get("tags") or [])
        route = self._build_route(
            target_type="cocoon",
            target_id=str(target["target_id"]),
            message_kind="private",
            account_id=account_id,
            conversation_id=conversation_id,
            tags=tags,
        )
        try:
            await self._upsert_backend_route(route)
        except Exception as exc:  # noqa: BLE001
            return f"Failed to sync route: {exc}"
        self.route_store.save_binding(
            "private",
            account_id,
            conversation_id,
            route=route,
            attached=True,
            tags=tags,
        )
        self.route_store.upsert_target(
            target_type="cocoon",
            target_id=str(target["target_id"]),
            name=str(target.get("name") or target["target_id"]),
        )
        return f"Attached to cocoon: {target.get('name') or target['target_id']}"

    async def _command_detach(self, payload: dict[str, Any], args: list[str]) -> str:
        del args
        account_id = str(payload["account_id"])
        conversation_id = str(payload["conversation_id"])
        existing = self.route_store.get_binding("private", account_id, conversation_id)
        if not existing or not existing.get("route"):
            return "No active private attachment."
        try:
            await self._delete_backend_route(
                message_kind="private",
                account_id=account_id,
                conversation_id=conversation_id,
            )
        except Exception as exc:  # noqa: BLE001
            return f"Failed to sync route: {exc}"
        self.route_store.save_binding(
            "private",
            account_id,
            conversation_id,
            route=dict(existing.get("route") or {}),
            attached=False,
            tags=list(existing.get("tags") or []),
        )
        return "Private attachment removed."

    def _command_tag(self, payload: dict[str, Any], args: list[str]) -> str:
        account_id = str(payload["account_id"])
        conversation_id = str(payload["conversation_id"])
        binding = self.route_store.get_binding("private", account_id, conversation_id)
        if not binding or not binding.get("route"):
            return "No private target is attached."
        current_tags = list(binding.get("tags") or [])
        if not args or args[0].lower() == "list":
            return f"tags: {', '.join(current_tags) or '-'}"
        action = args[0].lower()
        values = [item.strip() for item in args[1:] if item.strip()]
        if action == "add":
            next_tags = list(dict.fromkeys(current_tags + values))
        elif action == "remove":
            remove_set = set(values)
            next_tags = [item for item in current_tags if item not in remove_set]
        elif action == "clear":
            next_tags = []
        else:
            return "Usage: /tag [list|add|remove|clear] ..."
        self.route_store.update_binding_tags(
            "private", account_id, conversation_id, next_tags
        )
        route = dict(binding.get("route") or {})
        target_id = str(route.get("target_id") or "")
        target = self.route_store.get_target(target_id)
        if target is not None:
            self.route_store.upsert_target(
                target_type=str(
                    target.get("target_type") or route.get("target_type") or ""
                ),
                target_id=target_id,
                name=str(target.get("name") or target_id),
                tags=next_tags,
            )
        return f"tags: {', '.join(next_tags) or '-'}"

    def _command_op_group_enable(self, payload: dict[str, Any], args: list[str]) -> str:
        if len(args) != 1:
            return "Usage: /op group enable <im_group_id>"
        group_id = str(args[0]).strip()
        if not group_id:
            return "Usage: /op group enable <im_group_id>"
        self.route_store.save_group_state(
            str(payload["account_id"]),
            group_id,
            enabled=True,
            attached=False,
            route=None,
            target_type="",
            target_id="",
            target_name="",
        )
        return f"Enabled IM group: {group_id}"

    async def _command_op_group_attach(
        self, payload: dict[str, Any], args: list[str]
    ) -> str:
        if len(args) != 2:
            return "Usage: /op group attach <im_group_id> <chat_group_id>"
        account_id = str(payload["account_id"])
        group_id = str(args[0]).strip()
        chat_group_id = str(args[1]).strip()
        if not group_id or not chat_group_id:
            return "Usage: /op group attach <im_group_id> <chat_group_id>"
        group_state = self.route_store.get_group_state(account_id, group_id)
        if not group_state or not group_state.get("enabled"):
            return "IM group is not enabled. Use /op group enable first."
        target, error = await self._resolve_target_by_id(
            payload,
            chat_group_id,
            allowed_types={"chat_group"},
        )
        if error:
            return error
        if target is None:
            return "Chat group not found or not visible."
        route = self._build_route(
            target_type="chat_group",
            target_id=chat_group_id,
            message_kind="group",
            account_id=account_id,
            conversation_id=group_id,
            tags=[],
        )
        try:
            await self._upsert_backend_route(route)
        except Exception as exc:  # noqa: BLE001
            return f"Failed to sync route: {exc}"
        self.route_store.upsert_target(
            target_type="chat_group",
            target_id=chat_group_id,
            name=str(target.get("name") or chat_group_id),
        )
        self.route_store.save_group_state(
            account_id,
            group_id,
            enabled=True,
            attached=True,
            route=route,
            target_type="chat_group",
            target_id=chat_group_id,
            target_name=str(target.get("name") or chat_group_id),
        )
        return f"Attached IM group {group_id} to chat_group {target.get('name') or chat_group_id}"

    async def _command_op_group_detach(
        self, payload: dict[str, Any], args: list[str]
    ) -> str:
        if len(args) != 1:
            return "Usage: /op group detach <im_group_id>"
        account_id = str(payload["account_id"])
        group_id = str(args[0]).strip()
        if not group_id:
            return "Usage: /op group detach <im_group_id>"
        group_state = self.route_store.get_group_state(account_id, group_id)
        if not group_state or not group_state.get("enabled"):
            return "IM group is not enabled."
        if not group_state.get("attached") or not group_state.get("route"):
            return "IM group is not attached."
        try:
            await self._delete_backend_route(
                message_kind="group",
                account_id=account_id,
                conversation_id=group_id,
            )
        except Exception as exc:  # noqa: BLE001
            return f"Failed to sync route: {exc}"
        self.route_store.save_group_state(
            account_id,
            group_id,
            enabled=True,
            attached=False,
            route=None,
            target_type="",
            target_id="",
            target_name="",
        )
        return f"Detached IM group: {group_id}"

    async def _command_op_group_disable(
        self, payload: dict[str, Any], args: list[str]
    ) -> str:
        if len(args) != 1:
            return "Usage: /op group disable <im_group_id>"
        account_id = str(payload["account_id"])
        group_id = str(args[0]).strip()
        if not group_id:
            return "Usage: /op group disable <im_group_id>"
        group_state = self.route_store.get_group_state(account_id, group_id)
        if group_state and group_state.get("attached") and group_state.get("route"):
            try:
                await self._delete_backend_route(
                    message_kind="group",
                    account_id=account_id,
                    conversation_id=group_id,
                )
            except Exception as exc:  # noqa: BLE001
                return f"Failed to sync route: {exc}"
        self.route_store.save_group_state(
            account_id,
            group_id,
            enabled=False,
            attached=False,
            route=None,
            target_type="",
            target_id="",
            target_name="",
        )
        return f"Disabled IM group: {group_id}"

    def _command_op_role_add(self, payload: dict[str, Any], args: list[str]) -> str:
        del payload
        if len(args) != 1 or not str(args[0]).strip():
            return "Usage: /op role add <im_uid>"
        user_id = str(args[0]).strip()
        current = self.route_store.add_op_user_id(user_id)
        return f"Granted OP to {user_id}. explicit_ops={len(current)}"

    def _command_op_role_remove(self, payload: dict[str, Any], args: list[str]) -> str:
        del payload
        if len(args) != 1 or not str(args[0]).strip():
            return "Usage: /op role remove <im_uid>"
        user_id = str(args[0]).strip()
        if user_id == str(self.config.get("im_owner_id") or "").strip():
            return "Cannot remove the configured im_owner_id from OP access."
        current = self.route_store.remove_op_user_id(user_id)
        return f"Removed OP from {user_id}. explicit_ops={len(current)}"
