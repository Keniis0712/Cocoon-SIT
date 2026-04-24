# QWeather Daily Alert

[English](README.md) | 简体中文

清单文件：`plugins/external/qweather_daily_alert/plugin.json`

## 用途

- 提供一个外部唤醒插件，用于拉取和风天气的预报和预警数据。
- 暴露短生命周期事件，用于生成当日天气摘要和天气预警摘要。

## 关键文件

- `main.py`：插件事件实现与远程 API 调用
- `plugin.json`：清单、配置 schema 和事件定义

## 必填用户配置

- `api_host`
- `project_id`
- `key_id`
- `private_key_pem`
- `weather_location`
- `alert_latitude`
- `alert_longitude`

可选配置包括 `lang`、`unit`、`jwt_ttl_seconds` 和 `local_time`。
