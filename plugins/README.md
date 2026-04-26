# Plugins

English | [简体中文](README.zh-CN.md)

This directory stores local example plugins used by the Cocoon-SIT plugin runtime.

## What Lives Here

- Source trees that can be packaged into plugin zip files for admin upload
- Example manifests that define the backend-facing plugin contract
- Minimal reference implementations for the two current plugin families:
  - IM bridge plugins
  - External wakeup/event plugins

## Runtime Model

- `external` plugins expose event functions declared in `plugin.json`
  - `short_lived` events run on demand or on a schedule and return a wakeup envelope
  - `daemon` events run as long-lived async tasks in a child process
- `im` plugins run as dedicated long-lived bridge processes and use the IM SDK to exchange inbound and outbound messages with Cocoon

More detail:

- [IM plugins](im/README.md)
- [External plugins](external/README.md)

## Packaging Checklist

Each plugin package uploaded to the admin backend should include:

- `plugin.json`
- the entry module declared by `entry_module`
- any helper packages or resource files used at runtime
- optional dependency metadata such as `requirements.txt`

The backend treats `plugin.json` as the source of truth for metadata, config schema, event declarations, and IM service entrypoints.

## Recommended Workflow

1. Edit the local source directory in this repo.
2. Confirm `plugin.json` matches the actual runtime entrypoints.
3. Package the plugin so the zip root contains `plugin.json` and the declared module files.
   - Versioned packages: `python scripts/package_plugins.py`
   - Dev package for one plugin: `python scripts/package_plugin_dev.py external/qweather_daily_alert`
4. Upload the zip in the admin plugin UI.
5. Configure plugin-level settings in admin.
6. For external plugins, configure event schedules or trigger manual runs.
7. For IM plugins, enable the plugin and verify the bridge process can connect to its external platform.

## Included Examples

- [`im/nonebot_onebot_v11_bridge`](im/nonebot_onebot_v11_bridge/README.md): IM bridge plugin for a NoneBot + OneBot V11 runtime
- [`external/qweather_daily_alert`](external/qweather_daily_alert/README.md): external wakeup plugin for QWeather forecast and alert events

## Related Backend Docs

- [`docs/backend/services/plugins/plugin-manifest.md`](../docs/backend/services/plugins/plugin-manifest.md)
- [`docs/backend/services/plugins/plugin-service.md`](../docs/backend/services/plugins/plugin-service.md)
- [`docs/backend/services/plugins/plugin-runtime-manager.md`](../docs/backend/services/plugins/plugin-runtime-manager.md)
