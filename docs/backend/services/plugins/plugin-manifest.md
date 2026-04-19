# Plugin Manifest

Source: `backend/app/services/plugins/manifest.py`

## Purpose

- Defines the zip package metadata contract consumed by the backend.
- Replaces any code-docstring-based event discovery with an explicit configuration file.

## Required Files

Each plugin zip must currently include:

- `plugin.json`
- plugin entry module source

Optional extras:

- dependency files
- resources/assets

## `plugin.json` Shape

Top-level fields:

- `name`
- `version`
- `display_name`
- `plugin_type`: `external | im`
- `entry_module`
- `config_schema`
- `default_config`

For `external` plugins:

- `events[]`
  - `name`
  - `mode`: `short_lived | daemon`
  - `function_name`
  - `title`
  - `description`
  - `config_schema`
  - `default_config`

For `im` plugins:

- `service_function`

## Notes

- `plugin.json` is the only trusted metadata source in v1.
- Frontend-generated forms should use the stored JSON Schema rather than infer config inputs from code.
- The generated `dependency_manifest.json` also records archived package paths, which the backend uses both for runtime bootstrap and for pruning unreferenced shared package versions during plugin deletion.
- The admin API exposes the archived package inventory through `/api/v1/admin/plugins/shared-libs`, including per-package reference counts derived from installed plugin manifests.
