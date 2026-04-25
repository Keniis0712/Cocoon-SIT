from __future__ import annotations

from typing import Any


class ImPluginRpcMixin:
    async def create_cocoon(
        self,
        *,
        name: str,
        owner_user_id: str | None = None,
        owner_username: str | None = None,
        character_id: str,
        selected_model_id: str,
        parent_id: str | None = None,
        default_temperature: float | None = None,
        max_context_messages: int | None = None,
        auto_compaction_enabled: bool | None = None,
    ) -> dict[str, Any]:
        owner_payload = self._single_identity_payload(
            id_value=owner_user_id,
            username_value=owner_username,
            id_key="owner_user_id",
            username_key="owner_username",
            subject="owner",
        )
        return await self._rpc(
            "create_cocoon",
            {
                "name": name,
                **owner_payload,
                "character_id": character_id,
                "selected_model_id": selected_model_id,
                "parent_id": parent_id,
                "default_temperature": default_temperature,
                "max_context_messages": max_context_messages,
                "auto_compaction_enabled": auto_compaction_enabled,
            },
        )

    async def create_chat_group(
        self,
        *,
        name: str,
        owner_user_id: str | None = None,
        owner_username: str | None = None,
        character_id: str,
        selected_model_id: str,
        initial_member_ids: list[str] | None = None,
        default_temperature: float | None = None,
        max_context_messages: int | None = None,
        auto_compaction_enabled: bool | None = None,
        external_platform: str | None = None,
        external_group_id: str | None = None,
        external_account_id: str | None = None,
    ) -> dict[str, Any]:
        owner_payload = self._single_identity_payload(
            id_value=owner_user_id,
            username_value=owner_username,
            id_key="owner_user_id",
            username_key="owner_username",
            subject="owner",
        )
        return await self._rpc(
            "create_chat_group",
            {
                "name": name,
                **owner_payload,
                "character_id": character_id,
                "selected_model_id": selected_model_id,
                "initial_member_ids": list(initial_member_ids or []),
                "default_temperature": default_temperature,
                "max_context_messages": max_context_messages,
                "auto_compaction_enabled": auto_compaction_enabled,
                "external_platform": external_platform,
                "external_group_id": external_group_id,
                "external_account_id": external_account_id,
            },
        )

    async def verify_user_binding(self, *, username: str, token: str) -> dict[str, Any]:
        return await self._rpc(
            "verify_user_binding",
            {
                "username": username,
                "token": token,
            },
        )

    async def list_accessible_targets(
        self, *, user_id: str | None = None, username: str | None = None
    ) -> dict[str, Any]:
        identity_payload = self._single_identity_payload(
            id_value=user_id,
            username_value=username,
            id_key="user_id",
            username_key="username",
            subject="user",
        )
        return await self._rpc(
            "list_accessible_targets",
            identity_payload,
        )

    async def list_accessible_characters(
        self, *, user_id: str | None = None, username: str | None = None
    ) -> dict[str, Any]:
        identity_payload = self._single_identity_payload(
            id_value=user_id,
            username_value=username,
            id_key="user_id",
            username_key="username",
            subject="user",
        )
        return await self._rpc(
            "list_accessible_characters",
            identity_payload,
        )

    async def upsert_im_target_route(
        self,
        *,
        target_type: str,
        target_id: str,
        external_platform: str,
        conversation_kind: str,
        external_account_id: str,
        external_conversation_id: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._rpc(
            "upsert_im_target_route",
            {
                "target_type": target_type,
                "target_id": target_id,
                "external_platform": external_platform,
                "conversation_kind": conversation_kind,
                "external_account_id": external_account_id,
                "external_conversation_id": external_conversation_id,
                "metadata_json": dict(metadata_json or {}),
            },
        )

    async def delete_im_target_route(
        self,
        *,
        external_platform: str,
        conversation_kind: str,
        external_account_id: str,
        external_conversation_id: str,
    ) -> dict[str, Any]:
        return await self._rpc(
            "delete_im_target_route",
            {
                "external_platform": external_platform,
                "conversation_kind": conversation_kind,
                "external_account_id": external_account_id,
                "external_conversation_id": external_conversation_id,
            },
        )
