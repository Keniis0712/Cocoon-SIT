# Plugins

[English](README.md) | 简体中文

这个目录存放 Cocoon-SIT 插件运行时使用的本地示例插件源码。

## 这里放的是什么

- 可打包上传到后台的插件源码目录
- 用来描述插件契约的 `plugin.json`
- 当前两类插件的参考实现：
  - IM 桥接插件
  - 外部唤醒 / 事件插件

## 运行模型

- `external` 插件通过 `plugin.json` 声明事件函数
  - `short_lived` 事件按手动或计划任务触发，返回一条唤醒事件 envelope
  - `daemon` 事件以长生命周期异步任务形式在子进程内运行
- `im` 插件以独立长驻进程运行，通过 IM SDK 与 Cocoon 交换入站和出站消息

展开说明：

- [IM 插件](im/README.zh-CN.md)
- [External 插件](external/README.zh-CN.md)

## 打包检查清单

上传到后台的插件 zip 一般至少应包含：

- `plugin.json`
- `entry_module` 指定的入口模块
- 运行时依赖的辅助包或资源文件
- 可选的依赖说明文件，例如 `requirements.txt`

后端会把 `plugin.json` 视为元数据、配置 schema、事件声明和 IM 服务入口的唯一可信来源。

## 推荐流程

1. 在仓库里修改本地插件源码目录。
2. 确认 `plugin.json` 与真实入口函数保持一致。
3. 打包插件，确保 zip 根目录就能看到 `plugin.json` 和入口模块。
4. 在后台插件管理界面上传 zip。
5. 在后台配置插件级设置。
6. 对 external 插件配置事件调度或手动触发运行。
7. 对 IM 插件启用后确认桥接进程能连上外部平台。

## 当前示例

- [`im/nonebot_onebot_v11_bridge`](im/nonebot_onebot_v11_bridge/README.zh-CN.md)：对接 NoneBot + OneBot V11 的 IM 桥接插件
- [`external/qweather_daily_alert`](external/qweather_daily_alert/README.zh-CN.md)：基于和风天气的外部唤醒插件

## 相关后端文档

- [`docs/backend/services/plugins/plugin-manifest.md`](../docs/backend/services/plugins/plugin-manifest.md)
- [`docs/backend/services/plugins/plugin-service.md`](../docs/backend/services/plugins/plugin-service.md)
- [`docs/backend/services/plugins/plugin-runtime-manager.md`](../docs/backend/services/plugins/plugin-runtime-manager.md)
