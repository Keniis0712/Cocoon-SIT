# QWeather Daily Alert

English | [简体中文](README.zh-CN.md)

Manifest: `plugins/external/qweather_daily_alert/plugin.json`

## Purpose

- Fetch forecast and alert data from QWeather
- Turn the remote data into short wakeup summaries plus structured payloads
- Provide ready-to-schedule example events for weather-related wakeups

## Execution Model

- Plugin type: `external`
- Entry module: `main`
- Settings validation: `validate_settings`

Declared events:

- `daily_forecast`
  - mode: `short_lived`
  - function: `daily_forecast`
- `weather_alerts`
  - mode: `short_lived`
  - function: `weather_alerts`

Both events run once per trigger and return a summary plus payload envelope.

## Key Files

- `main.py`: config validation, JWT creation, QWeather requests, and event functions
- `plugin.json`: manifest, user config schema, and event declarations

## Configuration Scope

- plugin-level config: empty in the current example
- user-level config: required, because requests depend on per-user QWeather credentials and location settings

## Required User Settings

- `api_host`: QWeather API host name without protocol
- `project_id`: QWeather project identifier used as JWT `sub`
- `key_id`: signing key id placed in JWT headers
- `private_key_pem`: Ed25519 private key in PEM format
- `weather_location`: location id or coordinate string for weather endpoints
- `alert_latitude`: latitude used by the alert endpoint
- `alert_longitude`: longitude used by the alert endpoint

Optional user settings:

- `lang`: response language, default `zh`
- `unit`: unit system, `m` or `i`, default `m`
- `jwt_ttl_seconds`: JWT lifetime in seconds, default `900`
- `local_time`: whether alert queries use local time, default `true`

## Validation Rules

The plugin validates:

- all required fields are present
- `private_key_pem` looks like a PEM private key
- `unit` is either `m` or `i`
- `jwt_ttl_seconds` is between `60` and `86400`

Validation errors are surfaced as user-visible plugin errors.

## Event Output

### `daily_forecast`

- Calls:
  - `/v7/weather/now`
  - `/v7/weather/3d`
- Returns:
  - `summary`: compact human-readable weather summary
  - `payload.kind`: `qweather_daily_forecast`
  - `payload.weather_now`
  - `payload.weather_daily`

### `weather_alerts`

- Calls:
  - `/weatheralert/v1/current/{latitude}/{longitude}`
- Returns:
  - `summary`: either a no-alert message or a numbered alert summary
  - `payload.kind`: `qweather_alerts`
  - `payload.weather_alerts`

## Example User Config

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

## Operational Notes

- Requests are always sent over `https://{api_host}`.
- JWT signing uses `EdDSA`.
- Non-`200` QWeather API responses are raised as runtime errors and surfaced back to the user.
- This example keeps event config empty; all behavior comes from user-level configuration.

## Troubleshooting

- `missing required settings`
  - one or more required user config fields are empty
- `private key is not PEM`
  - the `private_key_pem` value does not include a valid PEM header/footer
- `unit` validation failure
  - use only `m` or `i`
- `JWT generation failed`
  - confirm the key format and signing inputs are valid
- `request failed`
  - verify network reachability, DNS, and `api_host`
- API returned non-success `code`
  - inspect the returned QWeather body for credential, quota, or parameter errors
