# PluginService

Source: `backend/app/services/plugins/service/service.py`

## Purpose

- Owns plugin install, update, delete, enable/disable, and config persistence.
- Treats `plugin.json` inside the uploaded zip as the only metadata source.
- Keeps admin API handlers thin by centralizing zip parsing, version registration, and event definition writes.

## Current Responsibilities

- install plugin zip packages
- validate `plugin.json`
- build version directories under `.plugins/<name>/versions/<version>/`
- create `PluginDefinition`, `PluginVersion`, `PluginEventDefinition`, and `PluginEventConfig`
- update plugin-level config and event-level config
- list shared dependency warehouse packages for admin inspection
- switch active version during updates
- delete plugin rows plus on-disk version/data directories

## Public Interface

- `list_plugins(session)`
- `get_plugin_detail(session, plugin_id)`
- `install_plugin(session, upload)`
- `update_plugin(session, plugin_id, upload)`
- `enable_plugin(session, plugin_id)`
- `disable_plugin(session, plugin_id)`
- `delete_plugin(session, plugin_id)`
- `update_plugin_config(session, plugin_id, config_json)`
- `update_event_config(session, plugin_id, event_name, config_json)`
- `set_event_enabled(session, plugin_id, event_name, enabled)`

## Notes

- Dependency installation now uses a staging install plus package-level archival into `.plugins/shared_libs/<normalized-package-name>/<version>/`.
- `dependency_manifest.json` records both `paths` and a `packages` list so runtime bootstrap can reconstruct the plugin-specific `sys.path` while still reusing package payloads across plugin versions.
- Plugin deletion now prunes unreferenced shared package versions by scanning the remaining dependency manifests.
- Postgres and other migrated environments require Alembic revision `0007_plugin_system` or later before the plugin admin endpoints can be used.
- Update semantics are `stop -> install -> run`; if installation fails, the service restores the previous active version pointer.
