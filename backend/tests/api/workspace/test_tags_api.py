from sqlalchemy import select

from app.models import CocoonTagBinding, SessionState


def test_workspace_tag_routes_cover_bind_list_and_unbind(client, auth_headers, default_cocoon_id):
    create_tag = client.post(
        "/api/v1/tags",
        headers=auth_headers,
        json={"tag_id": "focus-workspace", "brief": "Workspace focus", "visibility": "private", "is_isolated": False, "meta_json": {}},
    )
    assert create_tag.status_code == 200, create_tag.text
    focus_tag_id = create_tag.json()["id"]

    bind = client.post(
        f"/api/v1/cocoons/{default_cocoon_id}/tags",
        headers=auth_headers,
        json={"tag_id": focus_tag_id},
    )
    assert bind.status_code == 200, bind.text

    listing = client.get(f"/api/v1/cocoons/{default_cocoon_id}/tags", headers=auth_headers)
    assert listing.status_code == 200, listing.text
    assert any(item["tag_id"] == focus_tag_id for item in listing.json())

    unbind = client.delete(f"/api/v1/cocoons/{default_cocoon_id}/tags/{focus_tag_id}", headers=auth_headers)
    assert unbind.status_code == 200, unbind.text
    assert unbind.json()["tag_id"] == focus_tag_id

    with client.app.state.container.session_factory() as session:
        assert session.scalar(
            select(CocoonTagBinding).where(CocoonTagBinding.cocoon_id == default_cocoon_id, CocoonTagBinding.tag_id == focus_tag_id)
        ) is None
        state = session.get(SessionState, default_cocoon_id)
        assert state is not None
        assert focus_tag_id not in state.active_tags_json
