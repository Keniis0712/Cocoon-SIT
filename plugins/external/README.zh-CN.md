# External Plugins

[English](README.md) | 简体中文

这个目录存放外部唤醒 / 事件插件。

## 用途

- 拉取第三方系统数据
- 生成唤醒摘要或结构化 payload
- 以手动触发或后台调度的方式运行

## Manifest 常见字段

external 插件清单通常包含：

- `plugin_type: "external"`
- `entry_module`
- `events[]`
- 可选的 `settings_validation_function`
- 插件级与用户级配置 schema

每个事件都要声明 `mode`：

- `short_lived`：运行一次并返回一条 envelope
- `daemon`：以异步任务形式持续运行，并通过运行时队列推送 envelope

## 常见职责

- 校验插件级和用户级配置
- 调用外部 API 或服务
- 把远端数据转换成简洁摘要和机器可读 payload
- 在校验或运行失败时返回清晰的用户可见错误

## 示例

- [`qweather_daily_alert`](qweather_daily_alert/README.zh-CN.md)
