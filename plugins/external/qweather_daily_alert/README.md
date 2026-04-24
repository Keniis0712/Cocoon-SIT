# QWeather Daily Alert

English | [简体中文](README.zh-CN.md)

Manifest: `plugins/external/qweather_daily_alert/plugin.json`

## Purpose

- Provides an external wakeup plugin that fetches forecast and alert data from QWeather.
- Exposes short-lived plugin events for daily forecast summaries and weather alerts.

## Key Files

- `main.py`: plugin event implementation and remote API calls
- `plugin.json`: manifest, settings schema, and event definitions

## Required User Settings

- `api_host`
- `project_id`
- `key_id`
- `private_key_pem`
- `weather_location`
- `alert_latitude`
- `alert_longitude`

Optional settings include `lang`, `unit`, `jwt_ttl_seconds`, and `local_time`.
