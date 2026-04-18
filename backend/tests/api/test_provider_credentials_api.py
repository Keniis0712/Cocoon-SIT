from sqlalchemy import select

from app.models import ModelProvider, ProviderCredential


def test_provider_credentials_are_encrypted_and_masked(client, auth_headers):
    providers = client.get("/api/v1/providers", headers=auth_headers)
    assert providers.status_code == 200
    provider_id = providers.json()[0]["id"]

    secret = "super-secret-provider-key"
    create = client.post(
        f"/api/v1/providers/{provider_id}/credentials",
        headers=auth_headers,
        json={"secret": secret, "metadata_json": {"label": "test"}},
    )
    assert create.status_code == 200, create.text
    assert secret not in create.text
    assert "*" in create.json()["masked_secret"]

    fetch = client.get(f"/api/v1/providers/{provider_id}/credentials", headers=auth_headers)
    assert fetch.status_code == 200
    assert secret not in fetch.text

    with client.app.state.container.session_factory() as session:
        credential = session.scalar(
            select(ProviderCredential).where(ProviderCredential.provider_id == provider_id)
        )
        assert credential is not None
        assert credential.secret_encrypted != secret
        provider = session.get(ModelProvider, provider_id)
        assert provider is not None
