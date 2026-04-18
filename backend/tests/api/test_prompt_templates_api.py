from sqlalchemy import select

from app.models import PromptTemplate, PromptTemplateRevision, Role, User
from app.services.security.encryption import hash_secret


def test_prompt_template_rejects_unknown_variables(client, auth_headers):
    response = client.post(
        "/api/v1/prompt-templates/generator",
        headers=auth_headers,
        json={
            "name": "Bad Generator",
            "description": "Should fail",
            "content": "Use {{ unknown_variable }}",
        },
    )
    assert response.status_code == 422
    assert "Unknown prompt variables" in response.text


def test_prompt_template_revision_updates_immediately(client, auth_headers):
    response = client.put(
        "/api/v1/prompt-templates/generator",
        headers=auth_headers,
        json={
            "name": "Generator Template",
            "description": "Updated",
            "content": "Reply with context {{ visible_messages }} and {{ runtime_event }}",
        },
    )
    assert response.status_code == 200, response.text

    listing = client.get("/api/v1/prompt-templates", headers=auth_headers)
    assert listing.status_code == 200
    generator = next(item for item in listing.json() if item["template_type"] == "generator")
    assert generator["active_revision"]["version"] >= 2

    with client.app.state.container.session_factory() as session:
        template = session.scalar(
            select(PromptTemplate).where(PromptTemplate.template_type == "generator")
        )
        revisions = list(
            session.scalars(
                select(PromptTemplateRevision).where(PromptTemplateRevision.template_id == template.id)
            ).all()
        )
        assert len(revisions) >= 2


def test_rbac_blocks_prompt_template_write_for_operator(client):
    with client.app.state.container.session_factory() as session:
        operator_role = session.scalar(select(Role).where(Role.name == "operator"))
        user = User(
            username="operator",
            email="operator@example.com",
            password_hash=hash_secret("operator"),
            role_id=operator_role.id,
        )
        session.add(user)
        session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "operator"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.put(
        "/api/v1/prompt-templates/generator",
        headers=headers,
        json={
            "name": "Generator Template",
            "description": "Operator should not update",
            "content": "Reply with {{ visible_messages }}",
        },
    )
    assert response.status_code == 403
