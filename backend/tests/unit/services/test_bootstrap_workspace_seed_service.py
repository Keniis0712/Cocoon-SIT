from app.services.bootstrap_workspace_seed_service import BootstrapWorkspaceSeedService


def test_bootstrap_workspace_seed_service_is_a_noop():
    service = BootstrapWorkspaceSeedService()

    assert service.ensure_defaults(
        session=object(),
        owner_user_id="user-1",
        character_id="character-1",
        model_id="model-1",
    ) is None
