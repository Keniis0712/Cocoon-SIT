from __future__ import annotations

import io
import json
from zipfile import ZipFile

from sqlalchemy import select

from app.models import (
    AvailableModel,
    Character,
    ChatGroupMember,
    ChatGroupRoom,
    Cocoon,
    Role,
    SessionState,
    User,
    UserGroup,
    UserGroupMember,
)
from app.services.security.encryption import hash_secret


def _plugin_zip(*, manifest: dict, sources: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as bundle:
        bundle.writestr("plugin.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for path, content in sources.items():
            bundle.writestr(path, content)
    return buffer.getvalue()


def _login(client, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _ensure_user_with_role(client, *, username: str, password: str, role_name: str) -> str:
    container = client.app.state.container
    with container.session_factory() as session:
        role = session.scalar(select(Role).where(Role.name == role_name))
        assert role is not None
        user = session.scalar(select(User).where(User.username == username))
        if not user:
            user = User(
                username=username,
                email=f"{username}@example.com",
                password_hash=hash_secret(password),
                role_id=role.id,
                is_active=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        return user.id


def _create_user_cocoon(client, *, user_id: str, name: str) -> str:
    container = client.app.state.container
    with container.session_factory() as session:
        character = session.scalar(select(Character).order_by(Character.created_at.asc()))
        model = session.scalar(select(AvailableModel).order_by(AvailableModel.created_at.asc()))
        assert character is not None
        assert model is not None
        cocoon = Cocoon(
            name=name,
            owner_user_id=user_id,
            character_id=character.id,
            selected_model_id=model.id,
        )
        session.add(cocoon)
        session.flush()
        session.add(
            SessionState(
                cocoon_id=cocoon.id,
                relation_score=50,
                persona_json={},
                active_tags_json=[],
            )
        )
        session.commit()
        return cocoon.id


def _create_chat_group_with_admin_member(client, *, member_user_id: str, name: str) -> str:
    container = client.app.state.container
    with container.session_factory() as session:
        owner = session.scalar(select(User).where(User.username == "admin"))
        character = session.scalar(select(Character).order_by(Character.created_at.asc()))
        model = session.scalar(select(AvailableModel).order_by(AvailableModel.created_at.asc()))
        assert owner is not None
        assert character is not None
        assert model is not None
        room = ChatGroupRoom(
            name=name,
            owner_user_id=owner.id,
            character_id=character.id,
            selected_model_id=model.id,
        )
        session.add(room)
        session.flush()
        session.add(
            ChatGroupMember(
                room_id=room.id,
                user_id=member_user_id,
                member_role="admin",
            )
        )
        session.add(
            SessionState(
                chat_group_id=room.id,
                relation_score=50,
                persona_json={},
                active_tags_json=[],
            )
        )
        session.commit()
        return room.id


def test_user_can_manage_own_plugin_settings_with_group_visibility_override(client, auth_headers):
    install_payload = _plugin_zip(
        manifest={
            "name": "user-plugin",
            "version": "1.0.0",
            "display_name": "User Plugin",
            "plugin_type": "external",
            "entry_module": "main",
            "user_config_schema": {
                "type": "object",
                "required": ["location"],
                "properties": {"location": {"type": "string"}},
            },
            "user_default_config": {"location": "shanghai"},
            "settings_validation_function": "validate_settings",
            "events": [
                {
                    "name": "tick",
                    "mode": "short_lived",
                    "function_name": "tick",
                    "title": "Tick",
                    "description": "Tick event",
                    "config_schema": {"type": "object"},
                }
            ],
        },
        sources={
            "main.py": """
def tick(ctx):
    return None

def validate_settings(ctx):
    if (ctx.user_config or {}).get("location") == "mars":
        return "weather location not found"
    return None
""",
        },
    )
    install = client.post(
        "/api/v1/admin/plugins/install",
        headers=auth_headers,
        files={"file": ("plugin.zip", install_payload, "application/zip")},
    )
    assert install.status_code == 200, install.text
    plugin_id = install.json()["id"]

    normal_user_id = _ensure_user_with_role(client, username="plugin-user", password="pass123", role_name="user")
    user_headers = _login(client, "plugin-user", "pass123")

    container = client.app.state.container
    with container.session_factory() as session:
        group = UserGroup(name="plugin-test-group", owner_user_id=normal_user_id)
        session.add(group)
        session.flush()
        session.add(UserGroupMember(group_id=group.id, user_id=normal_user_id, member_role="member"))
        session.commit()
        group_id = group.id

    global_hidden = client.patch(
        f"/api/v1/admin/plugins/{plugin_id}/visibility",
        headers=auth_headers,
        json={"is_globally_visible": False},
    )
    assert global_hidden.status_code == 200, global_hidden.text
    assert global_hidden.json()["is_globally_visible"] is False

    group_visible = client.put(
        f"/api/v1/admin/plugins/{plugin_id}/groups/{group_id}/visibility",
        headers=auth_headers,
        json={"is_visible": True},
    )
    assert group_visible.status_code == 200, group_visible.text

    listing = client.get("/api/v1/plugins", headers=user_headers)
    assert listing.status_code == 200, listing.text
    row = next(item for item in listing.json() if item["id"] == plugin_id)
    assert row["is_visible"] is True
    assert row["is_enabled"] is True
    assert row["user_config_json"] == {"location": "shanghai"}

    bad_config = client.patch(
        f"/api/v1/plugins/{plugin_id}/config",
        headers=user_headers,
        json={"config_json": {"location": "mars"}},
    )
    assert bad_config.status_code == 200, bad_config.text
    assert bad_config.json()["user_error_text"] == "weather location not found"

    cleared = client.post(f"/api/v1/plugins/{plugin_id}/clear-error", headers=user_headers)
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["user_error_text"] is None

    disabled = client.post(f"/api/v1/plugins/{plugin_id}/disable", headers=user_headers)
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["is_enabled"] is False


def test_only_bootstrap_admin_can_manage_plugin_visibility(client, auth_headers, test_settings):
    install_payload = _plugin_zip(
        manifest={
            "name": "visibility-guard",
            "version": "1.0.0",
            "display_name": "Visibility Guard",
            "plugin_type": "external",
            "entry_module": "main",
            "events": [
                {
                    "name": "tick",
                    "mode": "short_lived",
                    "function_name": "tick",
                    "title": "Tick",
                    "description": "Tick event",
                    "config_schema": {"type": "object"},
                }
            ],
        },
        sources={"main.py": "def tick(ctx):\n    return None\n"},
    )
    install = client.post(
        "/api/v1/admin/plugins/install",
        headers=auth_headers,
        files={"file": ("plugin.zip", install_payload, "application/zip")},
    )
    assert install.status_code == 200, install.text
    plugin_id = install.json()["id"]

    container = client.app.state.container
    with container.session_factory() as session:
        role = Role(
            name="plugins-admin",
            permissions_json={"plugins:read": True, "plugins:write": True, "plugins:run": True},
        )
        session.add(role)
        session.flush()
        session.add(
            User(
                username="other-admin",
                email="other-admin@example.com",
                password_hash=hash_secret("pass123"),
                role_id=role.id,
                is_active=True,
            )
        )
        session.commit()

    other_admin_headers = _login(client, "other-admin", "pass123")
    blocked = client.patch(
        f"/api/v1/admin/plugins/{plugin_id}/visibility",
        headers=other_admin_headers,
        json={"is_globally_visible": False},
    )
    assert blocked.status_code == 403, blocked.text
    assert "bootstrap admin" in blocked.text

    allowed = client.patch(
        f"/api/v1/admin/plugins/{plugin_id}/visibility",
        headers=auth_headers,
        json={"is_globally_visible": False},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["is_globally_visible"] is False
    assert test_settings.default_admin_username == "admin"


def test_user_can_manage_own_plugin_wakeup_target_bindings(client, auth_headers, default_cocoon_id):
    install_payload = _plugin_zip(
        manifest={
            "name": "binding-plugin",
            "version": "1.0.0",
            "display_name": "Binding Plugin",
            "plugin_type": "external",
            "entry_module": "main",
            "events": [
                {
                    "name": "tick",
                    "mode": "short_lived",
                    "function_name": "tick",
                    "title": "Tick",
                    "description": "Tick event",
                    "config_schema": {"type": "object"},
                }
            ],
        },
        sources={"main.py": "def tick(ctx):\n    return {'summary': 'bound wakeup'}\n"},
    )
    install = client.post(
        "/api/v1/admin/plugins/install",
        headers=auth_headers,
        files={"file": ("plugin.zip", install_payload, "application/zip")},
    )
    assert install.status_code == 200, install.text
    plugin_id = install.json()["id"]

    user_id = _ensure_user_with_role(
        client,
        username="binding-user",
        password="pass123",
        role_name="user",
    )
    user_cocoon_id = _create_user_cocoon(client, user_id=user_id, name="User Binding Cocoon")
    user_headers = _login(client, "binding-user", "pass123")

    forbidden = client.post(
        f"/api/v1/plugins/{plugin_id}/targets",
        headers=user_headers,
        json={"target_type": "cocoon", "target_id": default_cocoon_id},
    )
    assert forbidden.status_code == 403, forbidden.text

    created = client.post(
        f"/api/v1/plugins/{plugin_id}/targets",
        headers=user_headers,
        json={"target_type": "cocoon", "target_id": user_cocoon_id},
    )
    assert created.status_code == 200, created.text
    binding = created.json()
    assert binding["target_type"] == "cocoon"
    assert binding["target_id"] == user_cocoon_id
    assert binding["scope_type"] == "user"
    assert binding["scope_id"] == user_id
    assert binding["target_name"]

    listing = client.get(f"/api/v1/plugins/{plugin_id}/targets", headers=user_headers)
    assert listing.status_code == 200, listing.text
    assert [item["id"] for item in listing.json()] == [binding["id"]]

    deleted = client.delete(f"/api/v1/plugins/{plugin_id}/targets/{binding['id']}", headers=user_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True

    room_id = _create_chat_group_with_admin_member(
        client,
        member_user_id=user_id,
        name="User Managed Group",
    )
    group_created = client.post(
        f"/api/v1/plugins/{plugin_id}/targets",
        headers=user_headers,
        json={"target_type": "chat_group", "target_id": room_id},
    )
    assert group_created.status_code == 200, group_created.text
    assert group_created.json()["target_type"] == "chat_group"
    assert group_created.json()["target_id"] == room_id
    assert group_created.json()["scope_type"] == "chat_group"
    assert group_created.json()["scope_id"] == room_id

    group_config = client.get(
        f"/api/v1/plugins/{plugin_id}/chat-groups/{room_id}/config",
        headers=user_headers,
    )
    assert group_config.status_code == 200, group_config.text
    assert group_config.json()["chat_group_id"] == room_id
    assert group_config.json()["is_enabled"] is True

    updated_group_config = client.patch(
        f"/api/v1/plugins/{plugin_id}/chat-groups/{room_id}/config",
        headers=user_headers,
        json={"config_json": {"api_key": "group-key"}},
    )
    assert updated_group_config.status_code == 200, updated_group_config.text
    assert updated_group_config.json()["config_json"] == {"api_key": "group-key"}

    disabled_group_config = client.post(
        f"/api/v1/plugins/{plugin_id}/chat-groups/{room_id}/disable",
        headers=user_headers,
    )
    assert disabled_group_config.status_code == 200, disabled_group_config.text
    assert disabled_group_config.json()["is_enabled"] is False
