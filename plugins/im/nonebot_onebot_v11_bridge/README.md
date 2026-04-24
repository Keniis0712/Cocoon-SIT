# NoneBot OneBot V11 Bridge

English | [简体中文](README.zh-CN.md)

Manifest: `plugins/im/nonebot_onebot_v11_bridge/plugin.json`

## Purpose

- Connect Cocoon-SIT to a NoneBot runtime that speaks OneBot V11
- Turn private and group platform messages into Cocoon inbound events
- Deliver Cocoon outbound replies back to OneBot private chats or groups

## Execution Model

- Plugin type: `im`
- Entry module: `main`
- Service function: `run`
- Settings validation: `validate_settings`

The bridge runs as a long-lived process. On startup it reloads locally persisted route bindings and tries to sync attached routes back to the backend.

## Key Files

- `main.py`: plugin entry module
- `nbbridge/bridge.py`: bridge runtime, command handling, route sync, and delivery logic
- `nbbridge/config.py`: configuration normalization and validation
- `nbbridge/store.py`: local persistence for targets, bindings, and platform-user bindings
- `plugin.json`: admin-facing manifest and config schema

## Plugin Configuration

Required fields:

- `driver`: NoneBot driver string, default `~aiohttp`
- `onebot_ws_urls`: one or more `ws://` or `wss://` URLs for the OneBot adapter
- `default_owner_username`: fallback Cocoon owner used before a private-chat platform user binds successfully
- `default_model_id`: model id used when this plugin creates new targets

Optional fields:

- `onebot_access_token`: OneBot access token
- `command_start`: command prefixes, default `["/"]`
- `command_sep`: command separators, default `["."]`
- `private_cocoon_name_prefix`: prefix for auto-created private cocoons, default `QQ`
- `group_room_name_prefix`: prefix for auto-created group rooms, default `QQ Group`
- `message_priority`: NoneBot message listener priority, default `95`

Validation rules:

- `onebot_ws_urls` must be non-empty
- every websocket URL must use `ws://` or `wss://`
- `default_owner_username` is required
- `default_model_id` is required

## Supported Commands

The bridge parses platform text commands using the configured command prefix.

- `/status`
  - show platform, conversation type, current binding state, and cached target count
- `/bind <username> <token>`
  - private chat only
  - verifies a Cocoon user binding token and stores the platform-user mapping locally
- `/unbind`
  - private chat only
  - removes the stored platform-user binding
- `/list [cocoons|targets|characters] [page]`
  - list attachable targets or available characters with pagination
- `/create [cocoon|group] [name] [character_name]`
  - in private chats the default target type is `cocoon`
  - in group chats the default target type is `chat_group`
- `/attach id <id>`
- `/attach name <name>`
  - private chats may attach only to `cocoon`
  - group chats may attach to either `cocoon` or `chat_group`
- `/detach`
  - remove the current platform route from the backend and mark the local binding as detached
- `/tag list`
- `/tag add <tag...>`
- `/tag remove <tag...>`
- `/tag clear`
  - manage tags stored on the local binding and propagated into route metadata

## Local State

The plugin writes `routes.json` under its runtime data directory. It stores:

- known targets cached from backend-visible targets
- per-conversation bindings
- private-chat platform-user bindings created by `/bind`

This cache allows the bridge to keep basic target references even if target listing temporarily fails.

## Behavior Notes

- Attached routes are synchronized back to the backend on plugin startup.
- Private incoming messages can resolve the sender/owner identity from a previously saved platform binding.
- Outbound replies are delivered through the IM SDK and translated into OneBot private or group send calls.
- When no specific bot account matches an outbound reply, the bridge falls back to the first connected bot.

## Example Operator Flow

1. Configure websocket URLs, default owner, and default model in admin.
2. Enable the plugin and confirm the NoneBot side is connected.
3. In a private chat, run `/bind <username> <token>` if you want platform messages to map to a real Cocoon user.
4. Run `/list characters` and `/create ...` if you need a new target.
5. Run `/attach id <id>` or `/attach name <name>` to connect the current conversation to a target.
6. Use `/status` to verify the current route and `/tag ...` to manage route tags.

## Troubleshooting

- `onebot_ws_urls must include at least one WebSocket URL`
  - add at least one valid `ws://` or `wss://` endpoint
- `default_owner_username is required`
  - set a fallback owner for new targets and pre-bind target discovery
- `default_model_id is required`
  - configure a model id before using `/create`
- `绑定失败`
  - confirm the username exists and the IM binding token is still valid
- `同步平台路由失败`
  - check backend plugin APIs and whether the plugin process can reach the Cocoon backend
- `找不到目标`
  - refresh the list with `/list` and attach by exact id if names are ambiguous
