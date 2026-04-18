from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import InviteCode, Role, User, UserGroup
from app.schemas.access.auth import RoleCreate, RoleUpdate, UserCreate, UserUpdate
from app.schemas.access.groups import GroupCreate, GroupMemberCreate
from app.schemas.access.invites import InviteCreate, InviteRedeemRequest


def test_user_and_role_services(client):
    container = client.app.state.container
    with container.session_factory() as session:
        role = container.role_service.create_role(
            session,
            RoleCreate(name="svc-role", permissions_json={"users:read": True}),
        )
        user = container.user_service.create_user(
            session,
            UserCreate(username="svc-user", email="svc-user@example.com", password="secret1", role_id=role.id, is_active=True),
        )
        session.commit()
        role_id = role.id
        user_id = user.id

    with container.session_factory() as session:
        updated_role = container.role_service.update_role(
            session,
            role_id,
            RoleUpdate(name="svc-role-2", permissions_json={"users:write": True}),
        )
        updated_user = container.user_service.update_user(
            session,
            user_id,
            UserUpdate(is_active=False, password="secret2"),
        )
        session.commit()
        assert updated_role.name == "svc-role-2"
        assert updated_user.is_active is False
        assert any(item.id == user_id for item in container.user_service.list_users(session))
        assert any(item.id == role_id for item in container.role_service.list_roles(session))


def test_group_and_invite_services(client):
    container = client.app.state.container
    with container.session_factory() as session:
        admin = session.scalars(select(User).where(User.username == "admin")).first()
        target_user = container.user_service.create_user(
            session,
            UserCreate(username="invitee", email="invitee@example.com", password="secret1", role_id=None, is_active=True),
        )
        group = container.group_service.create_group(session, GroupCreate(name="svc-group"))
        member = container.group_service.add_group_member(
            session,
            group.id,
            GroupMemberCreate(user_id=target_user.id, member_role="member"),
        )
        invite = container.invite_service.create_invite(
            session,
            InviteCreate(
                code="SVC-INVITE",
                quota_total=3,
                expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
            ),
            admin,
        )
        redeemed = container.invite_service.redeem_invite(
            session,
            "SVC-INVITE",
            InviteRedeemRequest(user_id=target_user.id, quota=2),
        )
        session.commit()
        assert member.group_id == group.id
        assert redeemed["quota_used"] == 2
        assert any(item.id == group.id for item in container.group_service.list_groups(session))
        assert any(item.id == invite.id for item in container.invite_service.list_invites(session))
