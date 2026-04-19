"""Chat-group room and membership management."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatGroupMember, ChatGroupRoom, User
from app.schemas.workspace.chat_groups import (
    ChatGroupMemberCreate,
    ChatGroupMemberUpdate,
    ChatGroupRoomCreate,
    ChatGroupRoomUpdate,
)
from app.services.catalog.system_settings_service import SystemSettingsService
from app.services.workspace.targets import ensure_session_state


class ChatGroupService:
    """Creates chat-group rooms and manages room membership."""

    def __init__(self, system_settings_service: SystemSettingsService) -> None:
        self.system_settings_service = system_settings_service

    def list_rooms(self, session: Session) -> list[ChatGroupRoom]:
        return list(session.scalars(select(ChatGroupRoom).order_by(ChatGroupRoom.created_at.asc())).all())

    def create_room(self, session: Session, payload: ChatGroupRoomCreate, user: User) -> ChatGroupRoom:
        self.system_settings_service.require_model_allowed(session, payload.selected_model_id)
        settings = self.system_settings_service.get_settings(session)
        room = ChatGroupRoom(
            name=payload.name,
            owner_user_id=user.id,
            character_id=payload.character_id,
            selected_model_id=payload.selected_model_id,
            default_temperature=(
                payload.default_temperature
                if payload.default_temperature is not None
                else settings.default_cocoon_temperature
            ),
            max_context_messages=(
                payload.max_context_messages
                if payload.max_context_messages is not None
                else settings.default_max_context_messages
            ),
            auto_compaction_enabled=(
                payload.auto_compaction_enabled
                if payload.auto_compaction_enabled is not None
                else settings.default_auto_compaction_enabled
            ),
            external_platform=payload.external_platform,
            external_group_id=payload.external_group_id,
            external_account_id=payload.external_account_id,
        )
        session.add(room)
        session.flush()
        session.add(ChatGroupMember(room_id=room.id, user_id=user.id, member_role="admin"))
        ensure_session_state(session, chat_group_id=room.id)
        session.flush()

        for member_id in payload.initial_member_ids:
            if member_id == user.id:
                continue
            existing = session.scalar(
                select(ChatGroupMember).where(
                    ChatGroupMember.room_id == room.id,
                    ChatGroupMember.user_id == member_id,
                )
            )
            if existing:
                continue
            session.add(ChatGroupMember(room_id=room.id, user_id=member_id, member_role="member"))
        session.flush()
        return room

    def update_room(self, session: Session, room: ChatGroupRoom, payload: ChatGroupRoomUpdate) -> ChatGroupRoom:
        if payload.selected_model_id is not None:
            self.system_settings_service.require_model_allowed(session, payload.selected_model_id)
            room.selected_model_id = payload.selected_model_id
        for field in (
            "name",
            "character_id",
            "default_temperature",
            "max_context_messages",
            "auto_compaction_enabled",
            "external_platform",
            "external_group_id",
            "external_account_id",
        ):
            value = getattr(payload, field)
            if value is not None:
                setattr(room, field, value)
        session.flush()
        return room

    def delete_room(self, session: Session, room: ChatGroupRoom) -> ChatGroupRoom:
        session.query(ChatGroupMember).filter(ChatGroupMember.room_id == room.id).delete()
        session.delete(room)
        session.flush()
        return room

    def list_members(self, session: Session, room_id: str) -> list[ChatGroupMember]:
        return list(
            session.scalars(
                select(ChatGroupMember)
                .where(ChatGroupMember.room_id == room_id)
                .order_by(ChatGroupMember.created_at.asc())
            ).all()
        )

    def add_member(
        self,
        session: Session,
        room: ChatGroupRoom,
        payload: ChatGroupMemberCreate,
    ) -> ChatGroupMember:
        existing = session.scalar(
            select(ChatGroupMember).where(
                ChatGroupMember.room_id == room.id,
                ChatGroupMember.user_id == payload.user_id,
            )
        )
        if existing:
            return existing
        member = ChatGroupMember(
            room_id=room.id,
            user_id=payload.user_id,
            member_role=payload.member_role,
        )
        session.add(member)
        session.flush()
        return member

    def update_member(
        self,
        session: Session,
        room: ChatGroupRoom,
        user_id: str,
        payload: ChatGroupMemberUpdate,
    ) -> ChatGroupMember:
        if room.owner_user_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Room owner role cannot be changed",
            )
        member = session.scalar(
            select(ChatGroupMember).where(
                ChatGroupMember.room_id == room.id,
                ChatGroupMember.user_id == user_id,
            )
        )
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat group member not found")
        member.member_role = payload.member_role
        session.flush()
        return member

    def remove_member(self, session: Session, room: ChatGroupRoom, user_id: str) -> ChatGroupMember:
        if room.owner_user_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Room owner cannot be removed",
            )
        member = session.scalar(
            select(ChatGroupMember).where(
                ChatGroupMember.room_id == room.id,
                ChatGroupMember.user_id == user_id,
            )
        )
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat group member not found")
        session.delete(member)
        session.flush()
        return member
