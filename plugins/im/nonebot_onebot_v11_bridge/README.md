# NoneBot OneBot V11 Bridge

English | [简体中文](README.zh-CN.md)

Manifest: `plugins/im/nonebot_onebot_v11_bridge/plugin.json`

## Purpose

- Provides an IM bridge plugin that connects Cocoon-SIT with a NoneBot runtime speaking OneBot V11.
- Supports websocket-based OneBot connections and Cocoon-side user binding tokens.

## Key Files

- `main.py`: plugin entry module
- `nbbridge/bridge.py`: bridge runtime and command handling
- `nbbridge/config.py`: plugin configuration helpers
- `nbbridge/store.py`: bridge persistence helpers

## Expected Configuration

- `driver`
- `onebot_ws_urls`
- `default_owner_username`
- `default_model_id`

Optional settings include access token, command prefixes, room naming prefixes, and message priority.
