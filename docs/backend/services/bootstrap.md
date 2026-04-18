# Bootstrap Compatibility Wrapper

Source: `backend/app/services/bootstrap.py`

## Purpose

- Preserves the historical `seed_default_data(session, settings, prompt_service)` entrypoint.
- Delegates real work to `BootstrapService`.

## Public Interface

- `seed_default_data(session, settings, prompt_service)`

## Interactions

- Used as a compatibility shim for older imports.
- Instantiates `BootstrapService` and forwards the call.

## Notes

- New code should prefer `BootstrapService` directly.
