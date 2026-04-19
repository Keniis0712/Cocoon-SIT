# BootstrapWorkspaceSeedService

Source: `backend/app/services/bootstrap_workspace_seed_service.py`

## Purpose

- Reserved hook for future workspace seeding.
- The current product no longer creates a default cocoon or `SessionState` during startup.

## Public Interface

- `ensure_defaults(session, owner_user_id, character_id, model_id) -> None`

## Interactions

- Called by `BootstrapService`.
- Currently acts as a no-op compatibility seam.

## Notes

- Test fixtures may still create explicit cocoon data, but startup bootstrap does not.
