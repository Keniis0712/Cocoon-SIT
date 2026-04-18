# BootstrapService

Source: `backend/app/services/bootstrap_service.py`

## Purpose

- Coordinates the complete default-data seeding flow for a fresh deployment.
- Splits bootstrap into access, catalog, and workspace seed stages.

## Public Interface

- `seed_default_data(session)`

## Interactions

- Built by `AppContainer`.
- Called during `bootstrap_schema_and_seed()` when `auto_seed_defaults` is enabled.
- Delegates concrete writes to the bootstrap subservices.

## Notes

- This service is intended to be idempotent so startup can safely re-run it.
