# Plugins

[English](README.md) | 简体中文

这个目录存放 Cocoon-SIT 插件运行时使用的本地示例插件。

## 目录结构

- `external/`：外部唤醒类或工具类插件
- `im/`：把 Cocoon 工作区连接到外部 IM 平台的桥接插件

## 约定

- 每个插件都以 `plugin.json` 作为清单入口。
- `main.py` 是清单里声明的运行入口模块。
- 可选的辅助包会和 `main.py` 放在同一插件目录下，并随插件版本一起打包。

## 当前示例

- `im/nonebot_onebot_v11_bridge`：对接 NoneBot + OneBot V11 的 IM 桥接插件
- `external/qweather_daily_alert`：基于和风天气的外部唤醒插件
