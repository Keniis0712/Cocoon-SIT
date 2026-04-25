from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import InviteCode, InviteQuotaAccount, InviteQuotaGrant, Role, User, UserGroup
from app.schemas.access.invites import InviteCreate, InviteGrantCreate, InviteQuotaUpdate, InviteRedeemRequest
from app.services.access.group_service import ROOT_GROUP_ID
from app.services.access.invite_service import InviteService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_invite_service_create_invite_validates_sources_and_lists_by_newest():
    session_factory = _session_factory()
    service = InviteService()

    with session_factory() as session:
        admin_role = Role(name="admin", permissions_json={})
        session.add(admin_role)
        session.flush()
        actor = User(username="actor", password_hash="hash", role_id=admin_role.id)
        target = User(username="target", password_hash="hash")
        group = UserGroup(name="team", owner_user_id=target.id)
        session.add_all([actor, target, group])
        session.flush()
        group.owner_user_id = target.id
        session.commit()
        actor_id = actor.id
        target_id = target.id
        group_id = group.id

    with session_factory() as session:
        actor = session.get(User, actor_id)
        target = session.get(User, target_id)
        assert actor is not None
        assert target is not None

        with pytest.raises(HTTPException) as user_quota_exceeded:
            service.create_invite(
                session,
                InviteCreate(prefix="user", quota_total=1, source_type="USER", registration_group_id=group_id),
                actor,
            )
        assert user_quota_exceeded.value.status_code == 400

        with pytest.raises(HTTPException) as missing_group_id:
            service.create_invite(
                session,
                InviteCreate(prefix="group", quota_total=1, source_type="GROUP", registration_group_id=group_id),
                actor,
            )
        assert missing_group_id.value.status_code == 400

        with pytest.raises(HTTPException) as unsupported_source:
            service.create_invite(
                session,
                InviteCreate(prefix="bad", quota_total=1, source_type="UNKNOWN", registration_group_id=group_id),
                actor,
            )
        assert unsupported_source.value.status_code == 400

        service.create_grant(
            session,
            InviteGrantCreate(target_type="USER", target_id=target.id, amount=3),
            actor,
        )
        service.create_grant(
            session,
            InviteGrantCreate(target_type="GROUP", target_id=group_id, amount=5),
            actor,
        )
        session.commit()

        user_scoped = service.create_invite(
            session,
            InviteCreate(
                prefix="userok",
                quota_total=2,
                source_type="USER",
                source_id=target.id,
                registration_group_id=group_id,
                expires_at=(datetime.now(UTC) + timedelta(days=2)).replace(tzinfo=None),
            ),
            actor,
        )
        group_scoped = service.create_invite(
            session,
            InviteCreate(
                prefix="groupok",
                quota_total=1,
                source_type="GROUP",
                source_id=group_id,
                registration_group_id=group_id,
                expires_at=(datetime.now(UTC) + timedelta(days=2)).replace(tzinfo=None),
            ),
            actor,
        )

        assert user_scoped.source_id == target.id
        assert user_scoped.registration_group_id == group_id
        assert user_scoped.created_for_user_id == actor.id
        assert group_scoped.source_id == group_id
        assert user_scoped.code.startswith("USEROK-")
        assert group_scoped.code.startswith("GROUPOK-")
        assert [item.code for item in service.list_invites(session)] == [group_scoped.code, user_scoped.code]


def test_invite_service_group_sources_require_existing_group_and_available_quota():
    session_factory = _session_factory()
    service = InviteService()

    with session_factory() as session:
        admin_role = Role(name="admin", permissions_json={})
        session.add(admin_role)
        session.flush()
        actor = User(username="actor", password_hash="hash", role_id=admin_role.id)
        owner = User(username="owner", password_hash="hash")
        session.add_all([actor, owner])
        session.flush()
        group = UserGroup(name="team", owner_user_id=owner.id)
        session.add(group)
        session.commit()
        actor_id = actor.id
        group_id = group.id

    with session_factory() as session:
        actor = session.get(User, actor_id)
        assert actor is not None

        with pytest.raises(HTTPException) as missing_group:
            service.create_invite(
                session,
                InviteCreate(
                    prefix="grpnope",
                    quota_total=1,
                    source_type="GROUP",
                    source_id="missing-group",
                    registration_group_id=group_id,
                ),
                actor,
            )
        assert missing_group.value.status_code == 404

        service.create_grant(
            session,
            InviteGrantCreate(target_type="GROUP", target_id=group_id, amount=1),
            actor,
        )
        session.commit()

        with pytest.raises(HTTPException) as quota_exceeded:
            service.create_invite(
                session,
                InviteCreate(
                    prefix="grpfail2",
                    quota_total=2,
                    source_type="GROUP",
                    source_id=group_id,
                    registration_group_id=group_id,
                ),
                actor,
            )
        assert quota_exceeded.value.status_code == 400


def test_invite_service_generates_unique_codes_from_prefix_and_accepts_explicit_code():
    session_factory = _session_factory()
    service = InviteService()

    with session_factory() as session:
        admin_role = Role(name="admin", permissions_json={})
        session.add(admin_role)
        session.flush()
        actor = User(username="actor", password_hash="hash", role_id=admin_role.id)
        session.add(actor)
        session.commit()
        actor_id = actor.id

    with session_factory() as session:
        actor = session.get(User, actor_id)
        assert actor is not None
        service.group_service.ensure_root_group(session)

        generated_one = service.create_invite(
            session,
            InviteCreate(prefix="ops team", registration_group_id=ROOT_GROUP_ID),
            actor,
        )
        generated_two = service.create_invite(
            session,
            InviteCreate(prefix="ops team", registration_group_id=ROOT_GROUP_ID),
            actor,
        )
        explicit = service.create_invite(
            session,
            InviteCreate(code="MANUAL-CODE", registration_group_id=ROOT_GROUP_ID),
            actor,
        )

        assert generated_one.code.startswith("OPS-TEAM-")
        assert generated_two.code.startswith("OPS-TEAM-")
        assert generated_one.code != generated_two.code
        assert explicit.code == "MANUAL-CODE"


def test_invite_service_revoke_grant_and_create_grant_validate_error_paths():
    session_factory = _session_factory()
    service = InviteService()

    with session_factory() as session:
        admin_role = Role(name="admin", permissions_json={})
        session.add(admin_role)
        session.flush()
        actor = User(username="actor", password_hash="hash", role_id=admin_role.id)
        user = User(username="member", password_hash="hash")
        session.add_all([actor, user])
        session.flush()
        group = UserGroup(name="team", owner_user_id=user.id)
        session.add(group)
        session.flush()
        session.add_all(
            [
                InviteCode(code="REV1", quota_total=1, revoked_at=datetime.now(UTC).replace(tzinfo=None)),
                InviteCode(code="USED1", quota_total=1, quota_used=1),
            ]
        )
        session.commit()
        actor_id = actor.id
        user_id = user.id

    with session_factory() as session:
        actor = session.get(User, actor_id)
        assert actor is not None

        with pytest.raises(HTTPException) as missing_invite:
            service.revoke_invite(session, "MISSING")
        assert missing_invite.value.status_code == 404

        with pytest.raises(HTTPException) as already_revoked:
            service.revoke_invite(session, "REV1")
        assert already_revoked.value.status_code == 400

        with pytest.raises(HTTPException) as already_used:
            service.revoke_invite(session, "USED1")
        assert already_used.value.status_code == 400

        with pytest.raises(HTTPException) as unsupported_target:
            service.create_grant(
                session,
                InviteGrantCreate(target_type="ORG", target_id="org-1", amount=1),
                actor,
            )
        assert unsupported_target.value.status_code == 400

        with pytest.raises(HTTPException) as missing_user:
            service.create_grant(
                session,
                InviteGrantCreate(target_type="USER", target_id="missing-user", amount=1),
                actor,
            )
        assert missing_user.value.status_code == 404

        grant = service.create_grant(
            session,
            InviteGrantCreate(target_type="USER", target_id=user_id, amount=2, note="welcome"),
            actor,
        )
        revoked = service.revoke_grant(session, grant.id, actor)
        assert grant.target_id == user_id
        assert grant.note == "welcome"
        assert revoked.revoked_at is not None
        assert [item.id for item in service.list_grants(session)] == [grant.id]


def test_invite_service_summary_and_redeem_cover_remaining_branches():
    session_factory = _session_factory()
    service = InviteService()

    with session_factory() as session:
        actor = User(username="actor", password_hash="hash")
        user = User(username="redeemer", password_hash="hash")
        session.add_all([actor, user])
        session.flush()
        group = UserGroup(name="group", owner_user_id=user.id)
        session.add(group)
        session.flush()

        session.add_all(
            [
                InviteCode(code="REVOKED", quota_total=1, revoked_at=datetime.now(UTC).replace(tzinfo=None)),
                InviteCode(
                    code="EXPIRED",
                    quota_total=1,
                    expires_at=(datetime.now(UTC) - timedelta(days=1)).replace(tzinfo=None),
                ),
                InviteCode(code="FULL", quota_total=1, quota_used=1),
                InviteCode(
                    code="READY",
                    quota_total=3,
                    created_by_user_id=actor.id,
                    registration_group_id=ROOT_GROUP_ID,
                ),
            ]
        )
        session.commit()
        user_id = user.id
        group_id = group.id

        with pytest.raises(HTTPException) as bad_summary:
            service.get_summary(session, "ORG", "org-1")
        assert bad_summary.value.status_code == 400

        service.create_grant(
            session,
            InviteGrantCreate(target_type="USER", target_id=user_id, amount=6),
            actor,
        )
        service.create_grant(
            session,
            InviteGrantCreate(target_type="GROUP", target_id=group_id, amount=1, is_unlimited=True),
            actor,
        )
        service.create_invite(
            session,
            InviteCreate(
                code="USERSRC",
                quota_total=2,
                source_type="USER",
                source_id=user_id,
                registration_group_id=group_id,
                expires_at=(datetime.now(UTC) + timedelta(days=1)).replace(tzinfo=None),
            ),
            actor,
        )
        session.commit()

        user_summary = service.get_summary(session, "USER", user_id)
        group_summary = service.get_summary(session, "GROUP", group_id)
        assert user_summary.invite_quota_remaining == 4
        assert group_summary.invite_quota_unlimited is True

        with pytest.raises(HTTPException) as revoked:
            service.redeem_invite(session, "REVOKED", InviteRedeemRequest(user_id=user_id, quota=1))
        assert revoked.value.status_code == 400

        with pytest.raises(HTTPException) as expired:
            service.redeem_invite(session, "EXPIRED", InviteRedeemRequest(user_id=user_id, quota=1))
        assert expired.value.status_code == 400

        with pytest.raises(HTTPException) as quota_exceeded:
            service.redeem_invite(session, "FULL", InviteRedeemRequest(user_id=user_id, quota=1))
        assert quota_exceeded.value.status_code == 400

        with pytest.raises(HTTPException) as missing_user:
            service.redeem_invite(session, "READY", InviteRedeemRequest(user_id="missing-user", quota=1))
        assert missing_user.value.status_code == 404

        redeemed = service.redeem_invite(session, "READY", InviteRedeemRequest(user_id=user_id, quota=2))
        ready_invite = session.scalar(select(InviteCode).where(InviteCode.code == "READY"))
        grant = session.scalar(select(InviteQuotaGrant).where(InviteQuotaGrant.invite_code_id == ready_invite.id))

        assert redeemed["quota_used"] == 2
        assert ready_invite is not None
        assert ready_invite.quota_used == 2
        assert grant is not None
        assert grant.target_id == user_id
        assert service.get_summary(session, "USER", user_id).invite_quota_remaining == 6


def test_invite_service_update_summary_requires_admin_and_updates_account():
    session_factory = _session_factory()
    service = InviteService()

    with session_factory() as session:
        admin_role = Role(name="admin", permissions_json={})
        member_role = Role(name="member", permissions_json={})
        session.add_all([admin_role, member_role])
        session.flush()
        admin = User(username="admin-user", password_hash="hash", role_id=admin_role.id)
        member = User(username="member-user", password_hash="hash", role_id=member_role.id)
        session.add_all([admin, member])
        session.flush()
        group = UserGroup(name="quota-group", owner_user_id=member.id)
        session.add(group)
        session.commit()
        admin_id = admin.id
        member_id = member.id
        group_id = group.id

    with session_factory() as session:
        admin = session.get(User, admin_id)
        member = session.get(User, member_id)
        assert admin is not None
        assert member is not None

        with pytest.raises(HTTPException) as forbidden:
            service.update_summary(
                session,
                "USER",
                member_id,
                InviteQuotaUpdate(invite_quota_remaining=9),
                member,
            )
        assert forbidden.value.status_code == 403

        user_summary = service.update_summary(
            session,
            "USER",
            member_id,
            InviteQuotaUpdate(invite_quota_remaining=9, invite_quota_unlimited=True),
            admin,
        )
        group_summary = service.update_summary(
            session,
            "GROUP",
            group_id,
            InviteQuotaUpdate(invite_quota_remaining=3, invite_quota_unlimited=False),
            admin,
        )
        user_account = session.scalar(
            select(InviteQuotaAccount).where(
                InviteQuotaAccount.target_type == "USER",
                InviteQuotaAccount.target_id == member_id,
            )
        )

        assert user_summary.invite_quota_remaining == 9
        assert user_summary.invite_quota_unlimited is True
        assert group_summary.invite_quota_remaining == 3
        assert group_summary.invite_quota_unlimited is False
        assert user_account is not None
        assert user_account.remaining_quota == 9
        assert user_account.is_unlimited is True
