# QWeather Daily Alert

[English](README.md) | 简体中文

清单文件：`plugins/external/qweather_daily_alert/plugin.json`

## 用途

- 拉取和风天气的预报和预警数据
- 将远端数据转换成唤醒摘要和结构化 payload
- 提供两个适合调度执行的天气类示例事件

## 运行模型

- 插件类型：`external`
- 入口模块：`main`
- 配置校验函数：`validate_settings`

当前声明的事件：

- `daily_forecast`
  - 模式：`short_lived`
  - 函数：`daily_forecast`
- `weather_alerts`
  - 模式：`short_lived`
  - 函数：`weather_alerts`

这两个事件都会在每次触发时运行一次，并返回摘要和 payload envelope。

## 关键文件

- `main.py`：配置校验、JWT 生成、QWeather 请求与事件函数实现
- `plugin.json`：清单、用户配置 schema 和事件声明

## 配置范围

- 插件级配置：当前示例为空
- 用户级配置：必填，因为请求依赖每个用户自己的和风天气凭证与位置参数

## 必填用户配置

- `api_host`：QWeather API 主机名，不带协议
- `project_id`：写入 JWT `sub` 的项目标识
- `key_id`：写入 JWT header 的签名 key id
- `private_key_pem`：Ed25519 私钥 PEM
- `weather_location`：天气接口使用的 location id 或坐标字符串
- `alert_latitude`：预警接口使用的纬度
- `alert_longitude`：预警接口使用的经度

可选用户配置：

- `lang`：响应语言，默认 `zh`
- `unit`：单位制，`m` 或 `i`，默认 `m`
- `jwt_ttl_seconds`：JWT 生命周期，默认 `900`
- `local_time`：预警接口是否按本地时间查询，默认 `true`

## 校验规则

插件会校验：

- 必填字段是否都存在
- `private_key_pem` 是否看起来像 PEM 私钥
- `unit` 是否为 `m` 或 `i`
- `jwt_ttl_seconds` 是否处于 `60` 到 `86400` 之间

校验失败会作为用户可见插件错误返回。

## 事件输出

### `daily_forecast`

- 调用接口：
  - `/v7/weather/now`
  - `/v7/weather/3d`
- 返回内容：
  - `summary`：简短可读的天气摘要
  - `payload.kind`：`qweather_daily_forecast`
  - `payload.weather_now`
  - `payload.weather_daily`

### `weather_alerts`

- 调用接口：
  - `/weatheralert/v1/current/{latitude}/{longitude}`
- 返回内容：
  - `summary`：无预警时返回提示语，有预警时返回编号汇总
  - `payload.kind`：`qweather_alerts`
  - `payload.weather_alerts`

## 示例用户配置

```json
{
  "api_host": "api.qweather.com",
  "project_id": "your-project-id",
  "key_id": "your-key-id",
  "private_key_pem": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----",
  "weather_location": "101010100",
  "alert_latitude": "39.9042",
  "alert_longitude": "116.4074",
  "lang": "zh",
  "unit": "m",
  "jwt_ttl_seconds": 900,
  "local_time": true
}
```

## 运行说明

- 请求始终发送到 `https://{api_host}`。
- JWT 使用 `EdDSA` 进行签名。
- QWeather 返回非 `200` 的业务码时，会被当作运行时错误返回给用户。
- 当前示例没有事件级配置，行为完全由用户级配置决定。

## 排障

- `missing required settings`
  - 有必填用户配置没有填写
- `private key is not PEM`
  - `private_key_pem` 没有合法的 PEM 头尾
- `unit` 校验失败
  - 只能填写 `m` 或 `i`
- `JWT generation failed`
  - 检查私钥格式和签名参数
- `request failed`
  - 检查网络连通性、DNS 和 `api_host`
- API 返回非成功 `code`
  - 查看 QWeather 返回体，通常能定位到凭证、配额或参数错误
