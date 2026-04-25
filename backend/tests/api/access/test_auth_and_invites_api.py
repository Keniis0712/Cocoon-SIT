import io
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import InviteCode, InviteQuotaGrant, Role, User, UserGroup


def test_auth_refresh_me_and_missing_bearer(client):
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    assert login.status_code == 200, login.text
    assert login.envelope_json()["code"] == "OK"
    refresh_token = login.json()["refresh_token"]
    access_token = login.json()["access_token"]

    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh.status_code == 200, refresh.text
    assert refresh.json()["refresh_token"] != refresh_token

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me.status_code == 200, me.text
    assert me.json()["username"] == "admin"
    assert me.json()["role_name"] == "admin"
    assert me.json()["timezone"] == "UTC"
    assert me.json()["permissions"]["cocoons:read"] is True

    update = client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"timezone": "Asia/Shanghai"},
    )
    assert update.status_code == 200, update.text
    assert update.json()["timezone"] == "Asia/Shanghai"

    missing = client.get("/api/v1/auth/me")
    assert missing.status_code == 401, missing.text
    payload = missing.json()
    assert payload["code"] == "AUTH_MISSING_BEARER"
    assert payload["msg"] == "Missing bearer token"
    assert payload["data"] is None


def test_auth_can_issue_short_lived_im_bind_token(client):
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    assert login.status_code == 200, login.text
    access_token = login.json()["access_token"]

    response = client.post("/api/v1/auth/me/im-bind-token", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["token"]
    assert payload["expires_in_seconds"] >= 0
    assert payload["expires_in_seconds"] <= 60
    assert payload["expires_at"]


def test_invites_api_crud_and_summary_routes(client, auth_headers):
    container = client.app.state.container
    with container.session_factory() as session:
        role = Role(name="invite-role", permissions_json={"users:read": True})
        session.add(role)
        session.flush()
        user = User(
            username="invite-api-user",
            email="invite-api-user@example.com",
            password_hash="hash",
            role_id=role.id,
        )
        group = UserGroup(name="invite-api-group", owner_user_id=user.id)
        session.add_all([user, group])
        session.commit()
        user_id = user.id
        group_id = group.id

    invite = client.post(
        "/api/v1/invites",
        headers=auth_headers,
        json={
            "prefix": "apiinv",
            "quota_total": 3,
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "registration_group_id": group_id,
        },
    )
    assert invite.status_code == 200, invite.text
    invite_code = invite.json()["code"]
    assert invite_code.startswith("APIINV-")

    invites = client.get("/api/v1/invites", headers=auth_headers)
    assert invites.status_code == 200, invites.text
    assert any(item["code"] == invite_code for item in invites.json())

    grant = client.post(
        "/api/v1/invites/grants",
        headers=auth_headers,
        json={"target_type": "USER", "target_id": user_id, "amount": 2, "is_unlimited": False, "note": "api"},
    )
    assert grant.status_code == 200, grant.text

    group_grant = client.post(
        "/api/v1/invites/grants",
        headers=auth_headers,
        json={"target_type": "GROUP", "target_id": group_id, "amount": 5, "is_unlimited": False},
    )
    assert group_grant.status_code == 200, group_grant.text

    grants = client.get("/api/v1/invites/grants", headers=auth_headers)
    assert grants.status_code == 200, grants.text
    assert any(item["target_id"] == user_id for item in grants.json())

    my_summary = client.get("/api/v1/invites/summary/me", headers=auth_headers)
    assert my_summary.status_code == 200, my_summary.text
    assert my_summary.json()["target_type"] == "USER"

    group_summary = client.get(f"/api/v1/invites/summary/groups/{group_id}", headers=auth_headers)
    assert group_summary.status_code == 200, group_summary.text
    assert group_summary.json()["target_id"] == group_id

    redeem = client.post(
        f"/api/v1/invites/{invite_code}/redeem",
        headers=auth_headers,
        json={"user_id": user_id, "quota": 1},
    )
    assert redeem.status_code == 200, redeem.text
    assert redeem.json()["quota_used"] == 1

    used_revoke = client.delete(f"/api/v1/invites/{invite_code}", headers=auth_headers)
    assert used_revoke.status_code == 400, used_revoke.text
    used_revoke_payload = used_revoke.json()
    assert used_revoke_payload["code"] == "USED_INVITES_CANNOT_BE_REVOKED"
    assert used_revoke_payload["msg"] == "Used invites cannot be revoked"
    assert used_revoke_payload["data"] is None

    unused_invite = client.post(
        "/api/v1/invites",
        headers=auth_headers,
        json={"prefix": "apiinv", "quota_total": 1, "registration_group_id": group_id},
    )
    assert unused_invite.status_code == 200, unused_invite.text
    unused_code = unused_invite.json()["code"]

    revoke = client.delete(f"/api/v1/invites/{unused_code}", headers=auth_headers)
    assert revoke.status_code == 200, revoke.text
    assert revoke.json()["code"] == unused_code

    revoked_grant = client.delete(f"/api/v1/invites/grants/{group_grant.json()['id']}", headers=auth_headers)
    assert revoked_grant.status_code == 200, revoked_grant.text
    assert revoked_grant.json()["revoked_at"] is not None

    with container.session_factory() as session:
        assert session.scalar(select(InviteCode).where(InviteCode.code == invite_code)) is not None
        assert session.scalar(select(InviteQuotaGrant).where(InviteQuotaGrant.target_id == user_id)) is not None
