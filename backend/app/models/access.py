from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonDefaultMixin, TimestampMixin
from app.models.identity import new_id


class Role(Base, TimestampMixin, JsonDefaultMixin):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    permissions_json: Mapped[dict[str, bool]] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[str | None] = mapped_column(ForeignKey("roles.id"), nullable=True)
    permissions_json: Mapped[dict[str, bool]] = mapped_column(JSON, default=JsonDefaultMixin.json_dict)
    timezone: Mapped[str] = mapped_column(String(128), default="UTC", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuthSession(Base, TimestampMixin):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class UserImBindToken(Base, TimestampMixin):
    __tablename__ = "user_im_bind_tokens"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class InviteCode(Base, TimestampMixin):
    __tablename__ = "invite_codes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_for_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="ADMIN_OVERRIDE")
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    registration_group_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quota_total: Mapped[int] = mapped_column(Integer, default=0)
    quota_used: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class InviteQuotaGrant(Base, TimestampMixin):
    __tablename__ = "invite_quota_grants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    invite_code_id: Mapped[str | None] = mapped_column(ForeignKey("invite_codes.id"), nullable=True)
    granted_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="ADMIN_OVERRIDE")
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_type: Mapped[str] = mapped_column(String(32), default="USER")
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    quota: Mapped[int] = mapped_column(Integer, default=1)
    is_unlimited: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class InviteQuotaAccount(Base, TimestampMixin):
    __tablename__ = "invite_quota_accounts"
    __table_args__ = (
        UniqueConstraint("target_type", "target_id", name="uq_invite_quota_accounts_target"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    target_type: Mapped[str] = mapped_column(String(32), default="USER")
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    remaining_quota: Mapped[int] = mapped_column(Integer, default=0)
    is_unlimited: Mapped[bool] = mapped_column(Boolean, default=False)


class UserGroup(Base, TimestampMixin):
    __tablename__ = "user_groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    parent_group_id: Mapped[str | None] = mapped_column(ForeignKey("user_groups.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserGroupMember(Base, TimestampMixin):
    __tablename__ = "user_group_members"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(ForeignKey("user_groups.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    member_role: Mapped[str] = mapped_column(String(32), default="member")
