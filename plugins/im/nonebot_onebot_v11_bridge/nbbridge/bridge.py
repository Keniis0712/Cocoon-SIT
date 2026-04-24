from __future__ import annotations

import asyncio
from concurrent.futures import Future
from dataclasses import asdict
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from queue import Empty, Queue
import threading
from typing import Any

from app.services.plugins.im_sdk import (
    ImDeliveryResult,
    ImGroupMessage,
    ImInboundRoute,
    ImOutboundReply,
    ImPluginContext,
    ImPrivateMessage,
)

from .config import PLUGIN_PLATFORM, normalize_config, validate_settings, utc_now_iso
from .store import RouteStore


class NoneBotOneBotBridge:
    LIST_PAGE_SIZE = 10

    def __init__(self, ctx: ImPluginContext) -> None:
        self.ctx = ctx
        self.config = normalize_config(ctx.plugin_config)
        self.route_store = RouteStore(Path(ctx.data_dir) / "routes.json")
        self.stop_event = threading.Event()
        self.outbound_replies: Queue[tuple[ImOutboundReply, Future[ImDeliveryResult]]] = Queue()
        self._bot_lock = threading.Lock()
        self._connected_bots: dict[str, Any] = {}

    def run(self) -> None:
        asyncio.run(self._sync_attached_routes())
        self.ctx.on_outbound_reply(self._handle_outbound_reply)
        control_thread = threading.Thread(
            target=self._run_control_loop_thread,
            name="nonebot-onebot-v11-control",
            daemon=True,
        )
        control_thread.start()
        try:
            self._run_nonebot_thread()
        finally:
            self.stop_event.set()
            control_thread.join(timeout=2)

    def _run_control_loop_thread(self) -> None:
        try:
            asyncio.run(self.ctx.run_forever())
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_runtime_error(f"IM control loop failed: {exc}")
            self.stop_event.set()

    async def _dispatch_inbound_event(self, payload: dict[str, Any]) -> None:
        kind = str(payload.get("message_kind") or "").strip()
        route = self._binding_route(payload)
        if route is None:
            return
        identity = self._inbound_identity(payload)
        if kind == "private":
            message = ImPrivateMessage(
                account_id=str(payload["account_id"]),
                conversation_id=str(payload["conversation_id"]),
                sender_id=str(payload.get("sender_id")) if payload.get("sender_id") is not None else None,
                sender_display_name=(
                    str(payload.get("sender_display_name")) if payload.get("sender_display_name") is not None else None
                ),
                text=str(payload["text"]),
                message_id=str(payload["message_id"]),
                occurred_at=str(payload["occurred_at"]),
                sender_user_id=identity["sender_user_id"],
                owner_user_id=identity["owner_user_id"],
                memory_owner_user_id=identity["memory_owner_user_id"],
                raw_payload=dict(payload.get("raw_payload") or {}),
                metadata_json=dict(payload.get("metadata_json") or {}),
            )
            await self.ctx.emit_private_message(route, message)
            return
        if kind == "group":
            message = ImGroupMessage(
                account_id=str(payload["account_id"]),
                conversation_id=str(payload["conversation_id"]),
                sender_id=str(payload.get("sender_id")) if payload.get("sender_id") is not None else None,
                sender_display_name=(
                    str(payload.get("sender_display_name")) if payload.get("sender_display_name") is not None else None
                ),
                text=str(payload["text"]),
                message_id=str(payload["message_id"]),
                occurred_at=str(payload["occurred_at"]),
                group_name=str(payload.get("group_name")) if payload.get("group_name") is not None else None,
                sender_user_id=identity["sender_user_id"],
                owner_user_id=identity["owner_user_id"],
                memory_owner_user_id=identity["memory_owner_user_id"],
                raw_payload=dict(payload.get("raw_payload") or {}),
                metadata_json=dict(payload.get("metadata_json") or {}),
            )
            await self.ctx.emit_group_message(route, message)

    async def _handle_outbound_reply(self, reply: ImOutboundReply) -> ImDeliveryResult:
        future: Future[ImDeliveryResult] = Future()
        self.outbound_replies.put((reply, future))
        try:
            return await asyncio.wait_for(asyncio.wrap_future(future), timeout=20)
        except asyncio.TimeoutError:
            return ImDeliveryResult(ok=False, error="Timed out waiting for NoneBot delivery", retryable=True)

    def _binding_route(self, payload: dict[str, Any]) -> ImInboundRoute | None:
        binding = self.route_store.get_binding(
            str(payload.get("message_kind") or ""),
            str(payload.get("account_id") or ""),
            str(payload.get("conversation_id") or ""),
        )
        if not binding or not bool(binding.get("attached")):
            return None
        route = dict(binding.get("route") or {})
        if not route:
            return None
        metadata_json = dict(route.get("metadata_json") or {})
        metadata_json["tags"] = list(binding.get("tags") or [])
        return ImInboundRoute(
            target_type=str(route.get("target_type") or ""),
            target_id=str(route.get("target_id") or ""),
            metadata_json=metadata_json,
        )

    def _platform_binding(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if str(payload.get("message_kind") or "") != "private":
            return None
        return self.route_store.get_platform_binding(
            str(payload.get("account_id") or ""),
            str(payload.get("conversation_id") or ""),
        )

    def _resolve_owner_identity(self, payload: dict[str, Any]) -> dict[str, str]:
        binding = self._platform_binding(payload)
        if binding and binding.get("platform_user_id"):
            return {"owner_user_id": str(binding["platform_user_id"])}
        return {"owner_username": str(self.config.get("default_owner_username") or "").strip()}

    def _owner_lookup_identity(self, payload: dict[str, Any]) -> dict[str, str]:
        owner_identity = self._resolve_owner_identity(payload)
        if "owner_user_id" in owner_identity:
            return {"user_id": str(owner_identity["owner_user_id"])}
        return {"username": str(owner_identity.get("owner_username") or "")}

    def _inbound_identity(self, payload: dict[str, Any]) -> dict[str, str | None]:
        binding = self._platform_binding(payload)
        platform_user_id = ""
        if binding is not None:
            platform_user_id = str(binding.get("platform_user_id") or "").strip()
        if not platform_user_id:
            return {
                "sender_user_id": None,
                "owner_user_id": None,
                "memory_owner_user_id": None,
            }
        return {
            "sender_user_id": platform_user_id,
            "owner_user_id": platform_user_id,
            "memory_owner_user_id": platform_user_id,
        }

    def _remember_bot(self, bot: Any) -> None:
        bot_id = str(getattr(bot, "self_id", "") or "")
        if not bot_id:
            return
        with self._bot_lock:
            self._connected_bots[bot_id] = bot

    def _select_bot(self, account_id: str | None) -> Any | None:
        with self._bot_lock:
            if account_id and account_id in self._connected_bots:
                return self._connected_bots[account_id]
            if not self._connected_bots:
                return None
            return next(iter(self._connected_bots.values()))

    def _run_nonebot_thread(self) -> None:
        try:
            self._apply_nonebot_env()
            import nonebot
            from nonebot import on_message
            from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
            from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

            nonebot.init()
            driver = nonebot.get_driver()
            driver.register_adapter(OneBotV11Adapter)
            sender_loop_started = False

            async def ensure_sender_loop() -> None:
                nonlocal sender_loop_started
                if sender_loop_started:
                    return
                sender_loop_started = True
                asyncio.create_task(self._nonebot_sender_loop())

            listener = on_message(priority=self.config["message_priority"], block=False)

            @listener.handle()
            async def _handle_message(bot, event) -> None:
                await ensure_sender_loop()
                self._remember_bot(bot)
                payload = self._normalize_onebot_event(bot, event, PrivateMessageEvent, GroupMessageEvent)
                if payload is None:
                    return
                if self._is_command(str(payload.get("text") or "")):
                    response = await self._handle_command(payload)
                    if response:
                        await self._send_direct_message(bot, event, response, PrivateMessageEvent, GroupMessageEvent)
                    return
                route = self._binding_route(payload)
                if route is None:
                    return
                await self._dispatch_inbound_event(payload)

            nonebot.run()
        except Exception as exc:  # noqa: BLE001
            self.ctx.report_runtime_error(f"NoneBot runtime failed: {exc}")
            self.stop_event.set()
            raise

    async def _nonebot_sender_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                reply, future = await asyncio.to_thread(self.outbound_replies.get, True, 0.2)
            except Empty:
                continue
            if future.done():
                continue
            bot = self._select_bot(reply.external_account_id)
            if bot is None:
                future.set_result(ImDeliveryResult(ok=False, error="No active OneBot bot connection", retryable=True))
                continue
            try:
                await self._send_onebot_reply(bot, reply)
            except Exception as exc:  # noqa: BLE001
                future.set_result(ImDeliveryResult(ok=False, error=str(exc), retryable=True))
                continue
            future.set_result(ImDeliveryResult(ok=True))

    async def _send_onebot_reply(self, bot: Any, reply: ImOutboundReply) -> None:
        conversation_kind = str(reply.metadata_json.get("conversation_kind") or "").strip()
        if conversation_kind == "group":
            group_id = int(str(reply.external_conversation_id or "").strip())
            await bot.send_group_msg(group_id=group_id, message=reply.reply_text)
            return
        user_target = str(reply.external_conversation_id or reply.external_sender_id or "").strip()
        if not user_target:
            raise RuntimeError("Missing OneBot private target user_id")
        await bot.send_private_msg(user_id=int(user_target), message=reply.reply_text)

    async def _send_direct_message(
        self,
        bot: Any,
        event: Any,
        message: str,
        private_event_type: Any,
        group_event_type: Any,
    ) -> None:
        if isinstance(event, group_event_type):
            await bot.send_group_msg(group_id=int(event.group_id), message=message)
            return
        if isinstance(event, private_event_type):
            await bot.send_private_msg(user_id=int(event.user_id), message=message)
            return
        await bot.send(event=event, message=message)

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
            sender_display_name = str(
                getattr(sender, "card", None) or getattr(sender, "nickname", None) or ""
            ).strip() or None
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
        os.environ["ONEBOT_WS_URLS"] = json.dumps(self.config["onebot_ws_urls"], ensure_ascii=False)
        os.environ["ONEBOT_ACCESS_TOKEN"] = self.config["onebot_access_token"]
        os.environ["COMMAND_START"] = json.dumps(self.config["command_start"], ensure_ascii=False)
        os.environ["COMMAND_SEP"] = json.dumps(self.config["command_sep"], ensure_ascii=False)
        os.environ["HOST"] = "127.0.0.1"
        os.environ["PORT"] = "8080"

    def _is_command(self, text: str) -> bool:
        return self._parse_command(text) is not None

    def _parse_command(self, text: str) -> dict[str, Any] | None:
        stripped = text.strip()
        if not stripped:
            return None
        prefix = next((item for item in self.config["command_start"] if stripped.startswith(item)), None)
        if prefix is None:
            return None
        body = stripped[len(prefix):].strip()
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
        binding = self.route_store.get_binding(message_kind, account_id, conversation_id)
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
        lines.append(f"目标名称：{(target or {}).get('name') or route.get('target_type') or '-'}")
        lines.append(f"标签：{', '.join(binding.get('tags') or []) or '-'}")
        return "\n".join(lines)

    async def _command_bind(self, payload: dict[str, Any], args: list[str]) -> str:
        if str(payload["message_kind"]) != "private":
            return "只有私聊里才能执行绑定。"
        if len(args) < 2:
            return "用法：/bind <用户名> <验证码>"
        try:
            binding = await self.ctx.verify_user_binding(username=str(args[0]), token=str(args[1]))
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
        character_id, name, character_error = await self._resolve_create_character_and_name(
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
            external_platform=PLUGIN_PLATFORM if payload["message_kind"] == "group" else None,
            external_group_id=payload["conversation_id"] if payload["message_kind"] == "group" else None,
            external_account_id=payload["account_id"] if payload["message_kind"] == "group" else None,
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
        items = [item for item in targets if item.get("target_type") == "cocoon"] if list_kind == "cocoons" else targets
        return self._render_target_page(payload, items, page, list_kind=list_kind, fetch_error=fetch_error)

    async def _command_attach(self, payload: dict[str, Any], args: list[str]) -> str:
        message_kind = str(payload["message_kind"])
        account_id = str(payload["account_id"])
        conversation_id = str(payload["conversation_id"])
        existing = self.route_store.get_binding(message_kind, account_id, conversation_id)
        target_type = ""
        target_id = ""
        target_name = ""
        allowed_types = self._attachable_target_types(message_kind)
        if args:
            attach_mode, attach_value, error = self._parse_attach_args(args)
            if error:
                return error
            target, error = await self._resolve_attach_target(payload, attach_mode, attach_value, allowed_types)
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
        existing = self.route_store.get_binding(message_kind, account_id, conversation_id)
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
        binding = self.route_store.get_binding(message_kind, account_id, conversation_id)
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
        self.route_store.update_binding_tags(message_kind, account_id, conversation_id, next_tags)
        route = dict(binding.get("route") or {})
        target_id = str(route.get("target_id") or "")
        target = self.route_store.get_target(target_id)
        if target is not None:
            self.route_store.upsert_target(
                target_type=str(target.get("target_type") or route.get("target_type") or ""),
                target_id=target_id,
                name=str(target.get("name") or target_id),
                tags=next_tags,
            )
        return f"标签：{', '.join(next_tags) or '-'}"

    def _resolve_create_type_and_args(self, payload: dict[str, Any], args: list[str]) -> tuple[str, list[str]]:
        if args:
            first = str(args[0]).strip().lower()
            if first == "cocoon":
                return "cocoon", args[1:]
            if first in {"chat_group", "group"}:
                return "chat_group", args[1:]
        return ("chat_group" if payload["message_kind"] == "group" else "cocoon"), args

    async def _resolve_create_character_and_name(self, payload: dict[str, Any], *, args: list[str]) -> tuple[str, str, str | None]:
        characters = await self._fetch_accessible_characters(payload)
        if not characters:
            return "", "", "当前没有可用角色，请先执行 /list characters。"
        explicit_ref = self._extract_explicit_character_ref(args, characters)
        name_parts = args[:-1] if explicit_ref is not None else args
        name = " ".join(name_parts).strip()
        if explicit_ref is not None:
            match = self._match_accessible_character(characters, explicit_ref)
            if match is None:
                return "", name, f"找不到角色：{explicit_ref}。先执行 /list characters。"
            return str(match["character_id"]), name, None
        if len(characters) == 1:
            return str(characters[0]["character_id"]), name, None
        return "", name, "请先执行 /list characters，然后使用 /create [名称] [character_name]。"

    def _extract_explicit_character_ref(self, args: list[str], characters: list[dict[str, Any]]) -> str | None:
        if not args:
            return None
        candidate = str(args[-1]).strip()
        if not candidate:
            return None
        if self._match_accessible_character(characters, candidate) is not None:
            return candidate
        return None

    def _match_accessible_character(self, characters: list[dict[str, Any]], ref: str) -> dict[str, Any] | None:
        normalized = str(ref).strip()
        if not normalized:
            return None
        matches = [item for item in characters if str(item.get("name") or "").strip().casefold() == normalized.casefold()]
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
            return "", 1, "用法：/list [cocoons|characters] [页码]"
        if len(args) < 2:
            return list_kind, 1, None
        page_raw = str(args[1]).strip()
        if not page_raw.isdigit():
            return "", 1, "页码必须是正整数。"
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
            return f"获取{heading_label}失败：{fetch_error}"
        if not items:
            return f"当前还没有可见{heading_label}。"
        binding = self.route_store.get_binding(
            str(payload["message_kind"]),
            str(payload["account_id"]),
            str(payload["conversation_id"]),
        )
        current_target_id = str(((binding or {}).get("route") or {}).get("target_id") or "")
        page_items, current_page, total_pages = self._paginate_items(items, page)
        lines = [f"{heading_label} 第 {current_page}/{total_pages} 页，共 {len(items)} 项"]
        if fetch_error:
            lines.append(f"获取平台列表失败，显示本地缓存：{fetch_error}")
        for index, item in enumerate(page_items, start=(current_page - 1) * self.LIST_PAGE_SIZE + 1):
            marker = "*" if item["target_id"] == current_target_id and (binding or {}).get("attached") else "-"
            tags = ", ".join(item.get("tags") or [])
            suffix = f" tags=[{tags}]" if tags else ""
            item_label = self._target_display_label(item, list_kind=list_kind)
            lines.append(
                f"{index}. {marker} {item_label}{suffix}".strip()
            )
        if total_pages > 1:
            lines.append(f"使用 /list {heading_label} {min(current_page + 1, total_pages)} 查看其他页。")
        return "\n".join(lines)

    def _render_character_page(self, items: list[dict[str, Any]], page: int) -> str:
        if not items:
            return "当前没有可用角色。"
        page_items, current_page, total_pages = self._paginate_items(items, page)
        lines = [f"characters 第 {current_page}/{total_pages} 页，共 {len(items)} 项"]
        for index, item in enumerate(page_items, start=(current_page - 1) * self.LIST_PAGE_SIZE + 1):
            name = str(item.get("name") or "").strip() or "未命名角色"
            lines.append(f"{index}. - {name}")
        if total_pages > 1:
            lines.append(f"使用 /list characters {min(current_page + 1, total_pages)} 查看其他页。")
        return "\n".join(lines)

    def _paginate_items(self, items: list[dict[str, Any]], page: int) -> tuple[list[dict[str, Any]], int, int]:
        total_pages = max((len(items) + self.LIST_PAGE_SIZE - 1) // self.LIST_PAGE_SIZE, 1)
        current_page = min(max(page, 1), total_pages)
        start = (current_page - 1) * self.LIST_PAGE_SIZE
        end = start + self.LIST_PAGE_SIZE
        return items[start:end], current_page, total_pages

    def _parse_target_ref(self, value: str) -> tuple[str, str] | None:
        raw = str(value).strip()
        if ":" not in raw:
            return None
        prefix, target_id = raw.split(":", 1)
        normalized_prefix = prefix.strip().lower()
        normalized_target_id = target_id.strip()
        if not normalized_target_id:
            return None
        if normalized_prefix == "cocoon":
            return "cocoon", normalized_target_id
        if normalized_prefix in {"chat_group", "group"}:
            return "chat_group", normalized_target_id
        return None

    def _target_display_label(self, item: dict[str, Any], *, list_kind: str) -> str:
        name = str(item.get("name") or "").strip()
        target_type = str(item.get("target_type") or "").strip()
        if list_kind == "cocoons":
            return name or "未命名 cocoon"
        prefix = target_type or "target"
        if name:
            return f"{prefix} {name}"
        return prefix

    def _attachable_target_types(self, message_kind: str) -> set[str]:
        if str(message_kind).strip() == "private":
            return {"cocoon"}
        return {"cocoon", "chat_group"}

    def _parse_attach_args(self, args: list[str]) -> tuple[str, str, str | None]:
        if len(args) < 2:
            return "", "", "用法：/attach id <id> 或 /attach name <name>。"
        mode = str(args[0]).strip().lower()
        value = " ".join(str(item).strip() for item in args[1:] if str(item).strip()).strip()
        if mode not in {"id", "name"} or not value:
            return "", "", "用法：/attach id <id> 或 /attach name <name>。"
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
            exact_matches = [item for item in candidates if str(item.get("target_id") or "").strip() == value]
        else:
            exact_matches = [
                item for item in candidates if str(item.get("name") or "").strip().casefold() == value.casefold()
            ]
        if len(exact_matches) == 1:
            return exact_matches[0], None
        if len(exact_matches) > 1:
            if mode == "name":
                return None, "同名目标不止一个，请改用 /attach id <id>。"
            return None, "同一个 ID 对应多个目标，请检查目标列表。"
        return None, None

    async def _list_attach_candidates(self, payload: dict[str, Any], allowed_types: set[str]) -> list[dict[str, Any]]:
        try:
            items = await self._fetch_accessible_targets(payload)
        except Exception:  # noqa: BLE001
            items = self.route_store.list_targets()
        filtered = [item for item in items if str(item.get("target_type") or "") in allowed_types]
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
        for item in self.route_store.list_bindings():
            binding = dict(item.get("binding") or {})
            if not binding.get("attached") or not binding.get("route"):
                continue
            try:
                await self._upsert_backend_route(dict(binding.get("route") or {}))
            except Exception as exc:  # noqa: BLE001
                self.ctx.report_runtime_error(f"Failed to sync attached route: {exc}")

    async def _upsert_backend_route(self, route: dict[str, Any]) -> None:
        metadata_json = dict(route.get("metadata_json") or {})
        await self.ctx.upsert_im_target_route(
            target_type=str(route.get("target_type") or "").strip(),
            target_id=str(route.get("target_id") or "").strip(),
            external_platform=str(metadata_json.get("platform") or "").strip(),
            conversation_kind=str(metadata_json.get("conversation_kind") or "").strip(),
            external_account_id=str(metadata_json.get("external_account_id") or "").strip(),
            external_conversation_id=str(metadata_json.get("external_conversation_id") or "").strip(),
            metadata_json=metadata_json,
        )

    async def _delete_backend_route(self, *, message_kind: str, account_id: str, conversation_id: str) -> None:
        await self.ctx.delete_im_target_route(
            external_platform=PLUGIN_PLATFORM,
            conversation_kind=message_kind,
            external_account_id=account_id,
            external_conversation_id=conversation_id,
        )

    def _private_cocoon_name_from_payload(self, payload: dict[str, Any]) -> str:
        display_name = str(
            payload.get("sender_display_name") or payload.get("sender_id") or payload.get("conversation_id") or ""
        ).strip()
        return f"{self.config['private_cocoon_name_prefix']} {display_name}".strip()

    async def _fetch_accessible_targets(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
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

    async def _fetch_accessible_characters(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
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


def run(ctx: ImPluginContext) -> None:
    bridge = NoneBotOneBotBridge(ctx)
    bridge.run()


__all__ = ["NoneBotOneBotBridge", "run", "validate_settings"]
