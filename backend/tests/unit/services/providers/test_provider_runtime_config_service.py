from types import SimpleNamespace

from app.services.providers.provider_runtime_config_service import ProviderRuntimeConfigService


def test_build_chat_config_merges_model_provider_and_decrypted_secret():
    cipher = SimpleNamespace(decrypt=lambda value: f"plain:{value}")
    service = ProviderRuntimeConfigService(cipher)
    session = SimpleNamespace(scalar=lambda query: SimpleNamespace(secret_encrypted="ciphertext"))
    provider = SimpleNamespace(
        id="provider-1",
        base_url="https://example.com",
        capabilities_json={"structured_output_method": "json_schema"},
    )
    model = SimpleNamespace(config_json={"temperature": 0.3})

    config = service.build_chat_config(session, provider, model)

    assert config == {
        "temperature": 0.3,
        "structured_output_method": "json_schema",
        "base_url": "https://example.com",
        "api_key": "plain:ciphertext",
    }


def test_build_chat_config_omits_api_key_when_no_credential():
    cipher = SimpleNamespace(decrypt=lambda value: f"plain:{value}")
    service = ProviderRuntimeConfigService(cipher)
    session = SimpleNamespace(scalar=lambda query: None)
    provider = SimpleNamespace(id="provider-1", base_url=None, capabilities_json={})
    model = SimpleNamespace(config_json={"top_p": 0.9})

    config = service.build_chat_config(session, provider, model)

    assert config == {
        "top_p": 0.9,
        "structured_output_method": "tool_calling",
        "base_url": None,
    }


def test_build_chat_config_model_config_can_override_provider_structured_output_method():
    cipher = SimpleNamespace(decrypt=lambda value: f"plain:{value}")
    service = ProviderRuntimeConfigService(cipher)
    session = SimpleNamespace(scalar=lambda query: None)
    provider = SimpleNamespace(
        id="provider-1",
        base_url="https://example.com",
        capabilities_json={"structured_output_method": "tool_calling"},
    )
    model = SimpleNamespace(config_json={"structured_output_method": "json_schema"})

    config = service.build_chat_config(session, provider, model)

    assert config["structured_output_method"] == "json_schema"


def test_build_embedding_config_merges_secret_when_present():
    cipher = SimpleNamespace(decrypt=lambda value: f"plain:{value}")
    service = ProviderRuntimeConfigService(cipher)
    embedding_provider = SimpleNamespace(config_json={"dimensions": 8}, secret_encrypted="cipher")

    config = service.build_embedding_config(embedding_provider)

    assert config == {"dimensions": 8, "api_key": "plain:cipher"}


def test_build_embedding_config_without_secret_keeps_base_config():
    cipher = SimpleNamespace(decrypt=lambda value: f"plain:{value}")
    service = ProviderRuntimeConfigService(cipher)
    embedding_provider = SimpleNamespace(config_json={"dimensions": 16}, secret_encrypted=None)

    assert service.build_embedding_config(embedding_provider) == {"dimensions": 16}
