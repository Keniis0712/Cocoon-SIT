# BootstrapCatalogSeedService

Source: `backend/app/services/bootstrap_catalog_seed_service.py`

## Purpose

- Seeds catalog-level defaults required for startup metadata.
- Ensures prompt metadata and the default tag exist.

## Public Interface

- `ensure_defaults(session, prompt_service) -> None`

## Interactions

- Called by `BootstrapService`.
- Uses `PromptTemplateService.ensure_defaults()` to seed prompt variables and templates.

## Notes

- Startup bootstrap no longer creates builtin model providers, default models, default characters, or default cocoons.
