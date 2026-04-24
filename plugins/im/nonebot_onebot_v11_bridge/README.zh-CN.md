# NoneBot OneBot V11 Bridge

[English](README.md) | 简体中文

清单文件：`plugins/im/nonebot_onebot_v11_bridge/plugin.json`

## 用途

- 提供一个 IM 桥接插件，把 Cocoon-SIT 接到支持 OneBot V11 的 NoneBot 运行时。
- 支持基于 WebSocket 的 OneBot 连接，以及 Cocoon 侧的用户绑定令牌流程。

## 关键文件

- `main.py`：插件入口模块
- `nbbridge/bridge.py`：桥接运行时与指令处理
- `nbbridge/config.py`：插件配置解析
- `nbbridge/store.py`：桥接持久化与状态存取

## 主要配置

- `driver`
- `onebot_ws_urls`
- `default_owner_username`
- `default_model_id`

可选配置包括访问令牌、命令前缀、房间命名前缀和消息优先级。
