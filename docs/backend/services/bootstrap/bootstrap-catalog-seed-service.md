# BootstrapCatalogSeedService

Source: `backend/app/services/bootstrap_catalog_seed_service.py`

## Purpose

- Seeds catalog-level defaults required for a runnable environment.
- Ensures prompt metadata, a mock provider, a default model, a default character, and the default tag exist.

## Public Interface

- `ensure_defaults(session, prompt_service, admin_user_id) -> tuple[AvailableModel, Character]`

## Interactions

- Called by `BootstrapService`.
- Uses `PromptTemplateService.ensure_defaults()` to seed prompt variables and templates.

## Notes

- The returned model and character are used by workspace seeding to build the initial cocoon.
