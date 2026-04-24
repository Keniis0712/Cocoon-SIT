# Plugins

English | [简体中文](README.zh-CN.md)

This directory holds local example plugins used by the Cocoon-SIT plugin runtime.

## Layout

- `external/`: external wakeup or utility plugins
- `im/`: IM bridge plugins that connect Cocoon workspaces to external messaging systems

## Conventions

- Every plugin package is anchored by a `plugin.json` manifest.
- `main.py` is the runtime entry module declared by the manifest.
- Optional helper packages live beside `main.py` and are bundled with the plugin version payload.

## Included Plugins

- `im/nonebot_onebot_v11_bridge`: IM bridge plugin for a NoneBot + OneBot V11 runtime
- `external/qweather_daily_alert`: external wakeup plugin for QWeather forecast and alert events
