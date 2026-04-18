# BootstrapAccessSeedService

Source: `backend/app/services/bootstrap_access_seed_service.py`

## Purpose

- Seeds default access-control primitives required for first login.
- Ensures the built-in `admin` and `operator` roles exist.
- Ensures the configured default admin user exists.

## Public Interface

- `ensure_defaults(session, settings) -> User`

## Interactions

- Called by `BootstrapService`.
- Uses `hash_secret(...)` to persist the bootstrap password securely.

## Notes

- This service does not create workspace content; it only establishes the access baseline.
