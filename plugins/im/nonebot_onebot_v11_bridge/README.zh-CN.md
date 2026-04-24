# NoneBot OneBot V11 Bridge

[English](README.md) | 简体中文

清单文件：`plugins/im/nonebot_onebot_v11_bridge/plugin.json`

## 用途

- 将 Cocoon-SIT 接入支持 OneBot V11 的 NoneBot 运行时
- 把私聊和群聊平台消息转换为 Cocoon 入站事件
- 把 Cocoon 出站回复投递回 OneBot 私聊或群聊

## 运行模型

- 插件类型：`im`
- 入口模块：`main`
- 服务函数：`run`
- 配置校验函数：`validate_settings`

这个桥接插件以长驻进程方式运行。启动时会重新加载本地持久化的路由绑定，并尝试把已附着的路由重新同步回后端。

## 关键文件

- `main.py`：插件入口模块
- `nbbridge/bridge.py`：桥接运行时、命令处理、路由同步和消息投递逻辑
- `nbbridge/config.py`：配置归一化与校验
- `nbbridge/store.py`：目标、绑定关系和平台用户绑定的本地持久化
- `plugin.json`：后台读取的清单和配置 schema

## 插件配置

必填字段：

- `driver`：NoneBot driver 字符串，默认 `~aiohttp`
- `onebot_ws_urls`：一个或多个 `ws://` / `wss://` 的 OneBot WebSocket 地址
- `default_owner_username`：私聊尚未绑定平台用户时用于兜底的 Cocoon owner
- `default_model_id`：插件创建新目标时使用的模型 id

可选字段：

- `onebot_access_token`：OneBot 访问令牌
- `command_start`：命令前缀，默认 `["/"]`
- `command_sep`：命令分隔符，默认 `["."]`
- `private_cocoon_name_prefix`：自动创建私聊 cocoon 时的名称前缀，默认 `QQ`
- `group_room_name_prefix`：自动创建群聊房间时的名称前缀，默认 `QQ Group`
- `message_priority`：NoneBot 消息监听优先级，默认 `95`

校验规则：

- `onebot_ws_urls` 不能为空
- 每个 websocket 地址都必须使用 `ws://` 或 `wss://`
- `default_owner_username` 必填
- `default_model_id` 必填

## 支持的命令

桥接插件会按配置的命令前缀解析平台文本命令。

- `/status`
  - 查看平台、会话类型、当前绑定状态和本地缓存目标数
- `/bind <username> <token>`
  - 仅私聊可用
  - 校验 Cocoon 用户绑定令牌，并把平台用户映射保存到本地
- `/unbind`
  - 仅私聊可用
  - 删除当前保存的平台用户绑定
- `/list [cocoons|targets|characters] [page]`
  - 分页列出可附着目标或可用角色
- `/create [cocoon|group] [name] [character_name]`
  - 在私聊里默认创建 `cocoon`
  - 在群聊里默认创建 `chat_group`
- `/attach id <id>`
- `/attach name <name>`
  - 私聊只能附着到 `cocoon`
  - 群聊可以附着到 `cocoon` 或 `chat_group`
- `/detach`
  - 从后端删除当前平台路由，并把本地绑定标记为未附着
- `/tag list`
- `/tag add <tag...>`
- `/tag remove <tag...>`
- `/tag clear`
  - 管理保存在本地绑定上的标签，并同步到路由 metadata

## 本地状态文件

插件会在运行时数据目录下写入 `routes.json`，其中保存：

- 从后端可见目标同步下来的本地缓存
- 每个会话的绑定关系
- 通过 `/bind` 建立的私聊平台用户绑定

这份缓存可以在后端目标列表临时拉取失败时保留基础目标引用能力。

## 行为说明

- 已附着路由会在插件启动时重新同步到后端。
- 私聊入站消息可以通过之前保存的平台绑定解析 sender / owner 身份。
- 出站回复通过 IM SDK 投递，再转换成 OneBot 私聊或群聊发送调用。
- 如果没有精确匹配的 bot 账号可用，桥接会退回到当前第一个已连接 bot。

## 典型操作流程

1. 在后台配置 websocket 地址、默认 owner 和默认 model。
2. 启用插件并确认 NoneBot 侧已经连上。
3. 如果希望平台消息映射到真实 Cocoon 用户，在私聊里执行 `/bind <username> <token>`。
4. 需要新目标时先执行 `/list characters`，再执行 `/create ...`。
5. 用 `/attach id <id>` 或 `/attach name <name>` 把当前会话接到目标上。
6. 用 `/status` 核对当前路由，用 `/tag ...` 维护路由标签。

## 排障

- `onebot_ws_urls must include at least one WebSocket URL`
  - 没有配置任何合法的 `ws://` / `wss://` 地址
- `default_owner_username is required`
  - 没有配置用于兜底的 owner，创建目标和预绑定目标查询都会受影响
- `default_model_id is required`
  - 在使用 `/create` 前需要先配置模型 id
- `绑定失败`
  - 检查用户名是否存在，以及 IM 绑定 token 是否已过期
- `同步平台路由失败`
  - 检查后端插件 API 是否正常，以及插件进程是否能访问 Cocoon 后端
- `找不到目标`
  - 先重新执行 `/list`，如果重名则优先用精确 id 附着
