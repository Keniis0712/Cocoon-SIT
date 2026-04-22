from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import InviteCode, InviteQuotaGrant, User, UserGroup
from app.schemas.access.invites import InviteCreate, InviteGrantCreate, InviteRedeemRequest
from app.services.access.invite_service import InviteService
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_invite_service_create_invite_validates_sources_and_lists_by_newest():
    session_factory = _session_factory()
    service = InviteService()

    with session_factory() as session:
        actor = User(username="actor", password_hash="hash")
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
                InviteCreate(prefix="user", quota_total=1, source_type="USER"),
                actor,
            )
        assert user_quota_exceeded.value.status_code == 400

        with pytest.raises(HTTPException) as missing_group_id:
            service.create_invite(
                session,
                InviteCreate(prefix="group", quota_total=1, source_type="GROUP"),
                actor,
            )
        assert missing_group_id.value.status_code == 400

        with pytest.raises(HTTPException) as unsupported_source:
            service.create_invite(
                session,
                InviteCreate(prefix="bad", quota_total=1, source_type="UNKNOWN"),
                actor,
            )
        assert unsupported_source.value.status_code == 400

        session.add(
            InviteQuotaGrant(
                granted_by_user_id=actor.id,
                target_type="USER",
                target_id=target.id,
                quota=3,
                is_unlimited=False,
            )
        )
        session.add(
            InviteQuotaGrant(
                granted_by_user_id=actor.id,
                target_type="GROUP",
                target_id=group_id,
                quota=5,
                is_unlimited=False,
            )
        )
        session.commit()

        user_scoped = service.create_invite(
            session,
            InviteCreate(prefix="userok", quota_total=2, source_type="USER", source_id=target.id),
            actor,
        )
        group_scoped = service.create_invite(
            session,
            InviteCreate(prefix="groupok", quota_total=1, source_type="GROUP", source_id=group_id),
            actor,
        )

        assert user_scoped.source_id == target.id
        assert user_scoped.created_for_user_id == actor.id
        assert group_scoped.source_id == group_id
        assert user_scoped.code.startswith("USEROK-")
        assert group_scoped.code.startswith("GROUPOK-")
        assert [item.code for item in service.list_invites(session)] == [group_scoped.code, user_scoped.code]


def test_invite_service_group_sources_require_existing_group_and_available_quota():
    session_factory = _session_factory()
    service = InviteService()

    with session_factory() as session:
        actor = User(username="actor", password_hash="hash")
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
                InviteCreate(prefix="grpnope", quota_total=1, source_type="GROUP", source_id="missing-group"),
                actor,
            )
        assert missing_group.value.status_code == 404

        session.add(
            InviteQuotaGrant(
                granted_by_user_id=actor.id,
                target_type="GROUP",
                target_id=group_id,
                quota=1,
                is_unlimited=False,
            )
        )
        session.commit()

        with pytest.raises(HTTPException) as quota_exceeded:
            service.create_invite(
                session,
                InviteCreate(prefix="grpfail2", quota_total=2, source_type="GROUP", source_id=group_id),
                actor,
            )
        assert quota_exceeded.value.status_code == 400


def test_invite_service_generates_unique_codes_from_prefix_and_accepts_explicit_code():
    session_factory = _session_factory()
    service = InviteService()

    with session_factory() as session:
        actor = User(username="actor", password_hash="hash")
        session.add(actor)
        session.commit()
        actor_id = actor.id

    with session_factory() as session:
        actor = session.get(User, actor_id)
        assert actor is not None

        generated_one = service.create_invite(session, InviteCreate(prefix="ops team"), actor)
        generated_two = service.create_invite(session, InviteCreate(prefix="ops team"), actor)
        explicit = service.create_invite(session, InviteCreate(code="MANUAL-CODE"), actor)

        assert generated_one.code.startswith("OPS-TEAM-")
        assert generated_two.code.startswith("OPS-TEAM-")
        assert generated_one.code != generated_two.code
        assert explicit.code == "MANUAL-CODE"


def test_invite_service_revoke_and_create_grant_validate_error_paths():
    session_factory = _session_factory()
    service = InviteService()

    with session_factory() as session:
        actor = User(username="actor", password_hash="hash")
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
        assert grant.target_id == user_id
        assert grant.note == "welcome"
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

        session.add(
            InviteQuotaGrant(
                granted_by_user_id=actor.id,
                target_type="USER",
                target_id=user.id,
                quota=6,
                is_unlimited=False,
            )
        )
        session.add(
            InviteQuotaGrant(
                granted_by_user_id=actor.id,
                target_type="GROUP",
                target_id=group.id,
                quota=0,
                is_unlimited=True,
            )
        )
        session.add_all(
            [
                InviteCode(code="USERSRC", quota_total=2, source_type="USER", source_id=user.id),
                InviteCode(code="REVOKED", quota_total=1, revoked_at=datetime.now(UTC).replace(tzinfo=None)),
                InviteCode(
                    code="EXPIRED",
                    quota_total=1,
                    expires_at=(datetime.now(UTC) - timedelta(days=1)).replace(tzinfo=None),
                ),
                InviteCode(code="FULL", quota_total=1, quota_used=1),
                InviteCode(code="READY", quota_total=3, created_by_user_id=actor.id),
            ]
        )
        session.commit()
        user_id = user.id
        group_id = group.id

        with pytest.raises(HTTPException) as bad_summary:
            service.get_summary(session, "ORG", "org-1")
        assert bad_summary.value.status_code == 400

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
