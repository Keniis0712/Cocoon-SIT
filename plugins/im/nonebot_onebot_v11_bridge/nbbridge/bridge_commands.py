from __future__ import annotations

from typing import Any

from .config import PLUGIN_PLATFORM


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
        parts = body.split()
        return {
            "name": parts[0].lower(),
            "args": parts[1:],
        }

    async def _handle_command(self, payload: dict[str, Any]) -> str:
        command = self._parse_command(str(payload.get("text") or ""))
        if command is None:
            return ""
        name = str(command["name"])
        args = list(command["args"])
        if name == "status":
            return self._command_status(payload)
        if name == "bind":
            return await self._command_bind(payload, args)
        if name == "unbind":
            return self._command_unbind(payload)
        if name == "create":
            return await self._command_create(payload, args)
        if name == "list":
            return await self._command_list(payload, args)
        if name == "attach":
            return await self._command_attach(payload, args)
        if name == "detach":
            return await self._command_detach(payload)
        if name == "tag":
            return self._command_tag(payload, args)
        return "可用命令：/status, /bind <用户名> <验证码>, /unbind, /list [cocoons|characters] [页码], /create [名称] [character_name], /attach id <id> | /attach name <name>, /detach, /tag [list|add|remove|clear] ..."
        return (
            "可用命令：/status、/bind <用户名> <验证码>、/unbind、/create [name]、/list、"
            "/attach <target_id|cocoon:id|chat_group:id>、/detach、/tag [list|add|remove|clear] ..."
        )

    def _command_status(self, payload: dict[str, Any]) -> str:
        message_kind = str(payload["message_kind"])
        account_id = str(payload["account_id"])
        conversation_id = str(payload["conversation_id"])
        binding = self.route_store.get_binding(
            message_kind, account_id, conversation_id
        )
        lines = [
            f"平台：{PLUGIN_PLATFORM}",
            f"会话类型：{message_kind}",
            f"机器人账号：{account_id}",
            f"会话 ID：{conversation_id}",
            f"已知目标数：{len(self.route_store.list_targets())}",
        ]
        platform_binding = self._platform_binding(payload)
        if message_kind == "private":
            if platform_binding:
                lines.append(
                    f"平台用户：{platform_binding.get('platform_username') or '-'} ({platform_binding.get('platform_user_id') or '-'})"
                )
            else:
                lines.append("平台用户：-")
        if not binding or not binding.get("route"):
            lines.append("已附着：否")
            lines.append("目标：无")
            return "\n".join(lines)
        route = dict(binding.get("route") or {})
        target = self.route_store.get_target(str(route.get("target_id") or ""))
        lines.append(f"已附着：{'是' if binding.get('attached') else '否'}")
        lines.append(f"目标类型：{route.get('target_type') or '-'}")
        lines.append(
            f"目标名称：{(target or {}).get('name') or route.get('target_type') or '-'}"
        )
        lines.append(f"标签：{', '.join(binding.get('tags') or []) or '-'}")
        return "\n".join(lines)

    async def _command_bind(self, payload: dict[str, Any], args: list[str]) -> str:
        if str(payload["message_kind"]) != "private":
            return "只有私聊里才能执行绑定。"
        if len(args) < 2:
            return "用法：/bind <用户名> <验证码>"
        try:
            binding = await self.ctx.verify_user_binding(
                username=str(args[0]), token=str(args[1])
            )
        except Exception as exc:  # noqa: BLE001
            return f"绑定失败：{exc}"
        self.route_store.save_platform_binding(
            str(payload["account_id"]),
            str(payload["conversation_id"]),
            platform_user_id=str(binding.get("user_id") or ""),
            platform_username=str(binding.get("username") or args[0]),
        )
        return f"已绑定平台用户：{binding.get('username') or args[0]}"

    def _command_unbind(self, payload: dict[str, Any]) -> str:
        if str(payload["message_kind"]) != "private":
            return "只有私聊里才能解除绑定。"
        self.route_store.clear_platform_binding(
            str(payload["account_id"]),
            str(payload["conversation_id"]),
        )
        return "已清除平台绑定。"

    async def _command_create(self, payload: dict[str, Any], args: list[str]) -> str:
        target_type, create_args = self._resolve_create_type_and_args(payload, args)
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
            return (
                f"已创建 cocoon\n"
                f"名称：{target['name']}\n"
                "可先执行 /list cocoons，再用 /attach 序号 进行附着"
            )
        if not name:
            name = self._group_room_name_from_payload(payload)
        room = await self.ctx.create_chat_group(
            name=name,
            **owner_identity,
            character_id=character_id,
            selected_model_id=self.config["default_model_id"],
            external_platform=PLUGIN_PLATFORM
            if payload["message_kind"] == "group"
            else None,
            external_group_id=payload["conversation_id"]
            if payload["message_kind"] == "group"
            else None,
            external_account_id=payload["account_id"]
            if payload["message_kind"] == "group"
            else None,
        )
        target = self.route_store.upsert_target(
            target_type="chat_group",
            target_id=str(room["id"]),
            name=str(room.get("name") or name),
        )
        return (
            f"已创建 chat_group\n"
            f"名称：{target['name']}\n"
            "可先执行 /list targets，再用 /attach 序号 进行附着"
        )

    async def _command_list(self, payload: dict[str, Any], args: list[str]) -> str:
        list_kind, page, error = self._parse_list_request(args)
        if error:
            return error
        if list_kind == "characters":
            try:
                characters = await self._fetch_accessible_characters(payload)
            except Exception as exc:  # noqa: BLE001
                return f"获取角色列表失败：{exc}"
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
        message_kind = str(payload["message_kind"])
        account_id = str(payload["account_id"])
        conversation_id = str(payload["conversation_id"])
        existing = self.route_store.get_binding(
            message_kind, account_id, conversation_id
        )
        target_type = ""
        target_id = ""
        target_name = ""
        allowed_types = self._attachable_target_types(message_kind)
        if args:
            attach_mode, attach_value, error = self._parse_attach_args(args)
            if error:
                return error
            target, error = await self._resolve_attach_target(
                payload, attach_mode, attach_value, allowed_types
            )
            if error:
                return error
            if target is None:
                return "找不到目标；先用 /list 查看，然后使用 /attach id <id> 或 /attach name <name>。"
            target_type = str(target["target_type"])
            target_id = str(target["target_id"])
            target_name = str(target.get("name") or target_id)
        else:
            return "用法：/attach id <id> 或 /attach name <name>。"
        tags = list((existing or {}).get("tags") or [])
        route = self._build_route(
            target_type=target_type,
            target_id=target_id,
            message_kind=message_kind,
            account_id=account_id,
            conversation_id=conversation_id,
            tags=tags,
        )
        try:
            await self._upsert_backend_route(route)
        except Exception as exc:  # noqa: BLE001
            return f"同步平台路由失败：{exc}"
        self.route_store.save_binding(
            message_kind,
            account_id,
            conversation_id,
            route=route,
            attached=True,
            tags=tags,
        )
        self.route_store.upsert_target(
            target_type=target_type,
            target_id=target_id,
            name=target_name or target_id,
        )
        return f"已附着到 {target_type}：{target_name or target_id}"

    async def _command_detach(self, payload: dict[str, Any]) -> str:
        message_kind = str(payload["message_kind"])
        account_id = str(payload["account_id"])
        conversation_id = str(payload["conversation_id"])
        existing = self.route_store.get_binding(
            message_kind, account_id, conversation_id
        )
        if not existing or not existing.get("route"):
            return "当前没有附着目标。"
        try:
            await self._delete_backend_route(
                message_kind=message_kind,
                account_id=account_id,
                conversation_id=conversation_id,
            )
        except Exception as exc:  # noqa: BLE001
            return f"同步平台路由失败：{exc}"
        self.route_store.save_binding(
            message_kind,
            account_id,
            conversation_id,
            route=dict(existing.get("route") or {}),
            attached=False,
            tags=list(existing.get("tags") or []),
        )
        return "已解除附着。"

    def _command_tag(self, payload: dict[str, Any], args: list[str]) -> str:
        message_kind = str(payload["message_kind"])
        account_id = str(payload["account_id"])
        conversation_id = str(payload["conversation_id"])
        binding = self.route_store.get_binding(
            message_kind, account_id, conversation_id
        )
        if not binding or not binding.get("route"):
            return "当前会话还没有目标，请先 attach。"
        current_tags = list(binding.get("tags") or [])
        if not args or args[0].lower() == "list":
            return f"标签：{', '.join(current_tags) or '-'}"
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
            return "用法：/tag [list|add|remove|clear] ..."
        self.route_store.update_binding_tags(
            message_kind, account_id, conversation_id, next_tags
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
        return f"标签：{', '.join(next_tags) or '-'}"
