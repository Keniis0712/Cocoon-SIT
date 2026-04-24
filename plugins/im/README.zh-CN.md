# IM Plugins

[English](README.md) | 简体中文

这个目录存放 IM 桥接插件。

## 用途

- 把外部消息平台接入 Cocoon 工作区
- 将平台入站消息映射到 Cocoon 目标
- 把 Cocoon 回复投递回外部平台

## Manifest 常见字段

IM 插件清单通常包含：

- `plugin_type: "im"`
- `entry_module`
- `service_function`
- 可选的 `settings_validation_function`
- 插件级 `config_schema` 与 `default_config`

IM 插件和 external 插件不同，不声明 `events[]`，而是以独立长驻桥接进程运行。

## 常见职责

- 维护平台连接
- 管理平台会话与 Cocoon 目标之间的映射
- 在插件数据目录中持久化本地桥接状态
- 在支持的场景下提供用户绑定或附着命令
- 通过 IM SDK 回传出站消息结果和错误信息

## 示例

- [`nonebot_onebot_v11_bridge`](nonebot_onebot_v11_bridge/README.zh-CN.md)
