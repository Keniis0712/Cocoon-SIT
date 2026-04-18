# BootstrapWorkspaceSeedService

Source: `backend/app/services/bootstrap_workspace_seed_service.py`

## Purpose

- Seeds the initial workspace used for first-run demos and smoke tests.
- Ensures both the default cocoon and its `SessionState` exist.

## Public Interface

- `ensure_defaults(session, owner_user_id, character_id, model_id) -> Cocoon`

## Interactions

- Called by `BootstrapService`.
- Depends on prior access/catalog seeding to provide owner, character, and model identifiers.

## Notes

- This service only creates the workspace shell; it does not enqueue runtime actions.
