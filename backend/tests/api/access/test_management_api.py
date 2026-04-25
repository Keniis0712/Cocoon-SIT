from sqlalchemy import select

from app.models import Role, User, UserGroup, UserGroupMember


def test_roles_users_and_groups_api_crud(client, auth_headers):
    role_response = client.post(
        "/api/v1/roles",
        headers=auth_headers,
        json={"name": "api-role", "permissions_json": {"users:read": True, "users:write": True}},
    )
    assert role_response.status_code == 200, role_response.text
    role_id = role_response.json()["id"]

    roles_response = client.get("/api/v1/roles", headers=auth_headers)
    assert roles_response.status_code == 200, roles_response.text
    assert any(item["id"] == role_id for item in roles_response.json())

    user_response = client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "username": "api-user",
            "email": "api-user@example.com",
            "password": "secret1",
            "role_id": role_id,
            "permissions_json": {"audits:read": True},
            "is_active": True,
        },
    )
    assert user_response.status_code == 200, user_response.text
    user_id = user_response.json()["id"]
    assert user_response.json()["permissions_json"]["audits:read"] is True
    assert user_response.json()["effective_permissions"]["users:write"] is True
    assert user_response.json()["effective_permissions"]["audits:read"] is True

    users_response = client.get("/api/v1/users", headers=auth_headers)
    assert users_response.status_code == 200, users_response.text
    assert any(item["id"] == user_id for item in users_response.json())

    role_update = client.patch(
        f"/api/v1/roles/{role_id}",
        headers=auth_headers,
        json={"name": "api-role-updated", "permissions_json": {"users:read": True}},
    )
    assert role_update.status_code == 200, role_update.text
    assert role_update.json()["name"] == "api-role-updated"

    user_update = client.patch(
        f"/api/v1/users/{user_id}",
        headers=auth_headers,
        json={"is_active": False, "password": "secret2", "permissions_json": {"users:write": False}},
    )
    assert user_update.status_code == 200, user_update.text
    assert user_update.json()["is_active"] is False
    assert user_update.json()["effective_permissions"]["users:write"] is False

    group_response = client.post(
        "/api/v1/groups",
        headers=auth_headers,
        json={"name": "api-group", "description": "api group"},
    )
    assert group_response.status_code == 200, group_response.text
    group_id = group_response.json()["id"]
    assert group_response.json()["group_path"]

    groups_response = client.get("/api/v1/groups", headers=auth_headers)
    assert groups_response.status_code == 200, groups_response.text
    assert any(item["id"] == group_id for item in groups_response.json())

    group_update = client.patch(
        f"/api/v1/groups/{group_id}",
        headers=auth_headers,
        json={"name": "api-group-updated", "description": "updated"},
    )
    assert group_update.status_code == 200, group_update.text
    assert group_update.json()["name"] == "api-group-updated"
    assert group_update.json()["description"] == "updated"

    member_add = client.post(
        f"/api/v1/groups/{group_id}/members",
        headers=auth_headers,
        json={"user_id": user_id, "member_role": "member"},
    )
    assert member_add.status_code == 200, member_add.text

    members_response = client.get(f"/api/v1/groups/{group_id}/members", headers=auth_headers)
    assert members_response.status_code == 200, members_response.text
    assert any(item["user_id"] == user_id for item in members_response.json())

    member_remove = client.delete(f"/api/v1/groups/{group_id}/members/{user_id}", headers=auth_headers)
    assert member_remove.status_code == 200, member_remove.text
    assert member_remove.json()["user_id"] == user_id

    group_delete = client.delete(f"/api/v1/groups/{group_id}", headers=auth_headers)
    assert group_delete.status_code == 200, group_delete.text
    assert group_delete.json()["id"] == group_id

    with client.app.state.container.session_factory() as session:
        assert session.get(Role, role_id) is not None
        assert session.get(User, user_id) is not None
        assert session.get(UserGroup, group_id) is None
        assert session.scalar(
            select(UserGroupMember).where(UserGroupMember.group_id == group_id, UserGroupMember.user_id == user_id)
        ) is None


def test_users_api_blocks_self_role_and_status_changes(client, auth_headers):
    with client.app.state.container.session_factory() as session:
        admin = session.scalar(select(User).where(User.username == "admin"))
        assert admin is not None
        admin_id = admin.id

    response = client.patch(
        f"/api/v1/users/{admin_id}",
        headers=auth_headers,
        json={"is_active": False},
    )

    assert response.status_code == 403, response.text
    assert response.envelope_json()["msg"] == "Users cannot change their own role, permissions, or active status"
