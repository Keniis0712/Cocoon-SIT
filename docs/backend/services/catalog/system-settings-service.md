# SystemSettingsService

Source: `backend/app/services/catalog/system_settings_service.py`

## Purpose

- Reads and updates system-wide catalog settings exposed through the admin/API surface.
- Keeps router handlers thin by centralizing validation and persistence for global settings records.

## Public Interface

- `get_settings(session)`
- `update_settings(session, payload)`

## Notes

- This service owns global settings semantics, not per-user overrides.
- API routes should treat it as the single write path for mutable system settings.
