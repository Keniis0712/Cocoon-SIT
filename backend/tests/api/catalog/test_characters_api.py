from sqlalchemy import select

from app.models import Character, CharacterAcl, User


def test_character_and_acl_api_crud(client, auth_headers):
    create_response = client.post(
        "/api/v1/characters",
        headers=auth_headers,
        json={
            "name": "API Character",
            "prompt_summary": "Created through the API",
            "settings_json": {"tone": "curious"},
        },
    )
    assert create_response.status_code == 200, create_response.text
    character_id = create_response.json()["id"]

    list_response = client.get("/api/v1/characters", headers=auth_headers)
    assert list_response.status_code == 200, list_response.text
    assert any(item["id"] == character_id for item in list_response.json())

    update_response = client.patch(
        f"/api/v1/characters/{character_id}",
        headers=auth_headers,
        json={"prompt_summary": "Updated through the API"},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["prompt_summary"] == "Updated through the API"

    with client.app.state.container.session_factory() as session:
        admin = session.scalar(select(User).where(User.username == "admin"))
        assert admin is not None
        admin_id = admin.id

    acl_create = client.post(
        f"/api/v1/characters/{character_id}/acl",
        headers=auth_headers,
        json={
            "subject_type": "user",
            "subject_id": admin_id,
            "can_read": True,
            "can_use": True,
        },
    )
    assert acl_create.status_code == 200, acl_create.text
    acl_id = acl_create.json()["id"]

    acl_list = client.get(f"/api/v1/characters/{character_id}/acl", headers=auth_headers)
    assert acl_list.status_code == 200, acl_list.text
    assert any(item["id"] == acl_id for item in acl_list.json())

    acl_delete = client.delete(f"/api/v1/characters/{character_id}/acl/{acl_id}", headers=auth_headers)
    assert acl_delete.status_code == 200, acl_delete.text
    assert acl_delete.json()["id"] == acl_id

    delete_response = client.delete(f"/api/v1/characters/{character_id}", headers=auth_headers)
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["id"] == character_id

    with client.app.state.container.session_factory() as session:
        assert session.get(Character, character_id) is None
        assert session.get(CharacterAcl, acl_id) is None
