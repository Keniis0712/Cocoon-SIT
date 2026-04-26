from __future__ import annotations

import json
import time
from typing import Any

import jwt
import requests

from app.services.plugins.errors import PluginUserVisibleError


REQUEST_TIMEOUT_SECONDS = 20
REQUEST_MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 1.5


def _setting(ctx, key: str, default: Any = "") -> Any:
    return (ctx.user_config or {}).get(key, default)


def _required_settings(ctx) -> dict[str, Any]:
    cfg = {
        "api_host": str(_setting(ctx, "api_host")).strip(),
        "project_id": str(_setting(ctx, "project_id")).strip(),
        "key_id": str(_setting(ctx, "key_id")).strip(),
        "private_key_pem": str(_setting(ctx, "private_key_pem")).strip(),
        "weather_location": str(_setting(ctx, "weather_location")).strip(),
        "alert_latitude": str(_setting(ctx, "alert_latitude")).strip(),
        "alert_longitude": str(_setting(ctx, "alert_longitude")).strip(),
        "lang": str(_setting(ctx, "lang", "zh") or "zh").strip(),
        "unit": str(_setting(ctx, "unit", "m") or "m").strip(),
        "jwt_ttl_seconds": int(_setting(ctx, "jwt_ttl_seconds", 900) or 900),
        "local_time": bool(_setting(ctx, "local_time", True)),
    }
    missing = [
        key
        for key in (
            "api_host",
            "project_id",
            "key_id",
            "private_key_pem",
            "weather_location",
            "alert_latitude",
            "alert_longitude",
        )
        if not cfg[key]
    ]
    if missing:
        raise PluginUserVisibleError(
            f"和风天气配置缺少必填项: {', '.join(missing)}",
            user_id=ctx.user_id,
        )
    if "BEGIN PRIVATE KEY" not in cfg["private_key_pem"]:
        raise PluginUserVisibleError(
            "和风天气私钥必须是 PEM PRIVATE KEY 格式。",
            user_id=ctx.user_id,
        )
    if cfg["unit"] not in {"m", "i"}:
        raise PluginUserVisibleError("和风天气 unit 只能是 m 或 i。", user_id=ctx.user_id)
    if cfg["jwt_ttl_seconds"] < 60 or cfg["jwt_ttl_seconds"] > 86400:
        raise PluginUserVisibleError(
            "和风天气 JWT TTL 必须在 60 到 86400 秒之间。",
            user_id=ctx.user_id,
        )
    return cfg


def _build_jwt(private_key_pem: str, project_id: str, key_id: str, ttl_seconds: int) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": project_id, "iat": now - 30, "exp": now - 30 + ttl_seconds},
        private_key_pem,
        algorithm="EdDSA",
        headers={"kid": key_id, "alg": "EdDSA"},
    )


def _is_retryable_request_error(exc: requests.RequestException) -> bool:
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return isinstance(status_code, int) and status_code >= 500


def _qweather_get(
    api_host: str,
    token: str,
    path: str,
    params: dict[str, Any] | None = None,
    *,
    allow_zero_result: bool = False,
) -> dict[str, Any]:
    last_request_error: requests.RequestException | None = None
    for attempt in range(1, REQUEST_MAX_ATTEMPTS + 1):
        try:
            resp = requests.get(
                f"https://{api_host}{path}",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()
            break
        except requests.RequestException as exc:
            last_request_error = exc
            if attempt < REQUEST_MAX_ATTEMPTS and _is_retryable_request_error(exc):
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue
            raise RuntimeError(
                f"和风天气请求失败: {exc} (attempts={attempt}/{REQUEST_MAX_ATTEMPTS})"
            ) from exc
        except ValueError as exc:
            raise RuntimeError("和风天气返回内容不是有效 JSON。") from exc
    else:
        raise RuntimeError(
            f"和风天气请求失败: {last_request_error} (attempts={REQUEST_MAX_ATTEMPTS}/{REQUEST_MAX_ATTEMPTS})"
        )

    code = data.get("code")
    zero_result = bool((data.get("metadata") or {}).get("zeroResult"))
    if allow_zero_result and zero_result:
        return data
    if code != "200":
        raise RuntimeError(
            f"和风天气 API 返回非成功 code={code}, body={json.dumps(data, ensure_ascii=False)}"
        )
    return data


def _token_and_config(ctx) -> tuple[str, dict[str, Any]]:
    cfg = _required_settings(ctx)
    try:
        token = _build_jwt(
            cfg["private_key_pem"],
            cfg["project_id"],
            cfg["key_id"],
            cfg["jwt_ttl_seconds"],
        )
    except Exception as exc:
        raise PluginUserVisibleError(f"和风天气 JWT 生成失败: {exc}", user_id=ctx.user_id) from exc
    return token, cfg


def _weather_now(api_host: str, token: str, cfg: dict[str, Any]) -> dict[str, Any]:
    return _qweather_get(
        api_host,
        token,
        "/v7/weather/now",
        {"location": cfg["weather_location"], "lang": cfg["lang"], "unit": cfg["unit"]},
    )


def _weather_daily(api_host: str, token: str, cfg: dict[str, Any]) -> dict[str, Any]:
    return _qweather_get(
        api_host,
        token,
        "/v7/weather/3d",
        {"location": cfg["weather_location"], "lang": cfg["lang"], "unit": cfg["unit"]},
    )


def _weather_alerts(api_host: str, token: str, cfg: dict[str, Any]) -> dict[str, Any]:
    return _qweather_get(
        api_host,
        token,
        f"/weatheralert/v1/current/{cfg['alert_latitude']}/{cfg['alert_longitude']}",
        {"lang": cfg["lang"], "localTime": str(cfg["local_time"]).lower()},
        allow_zero_result=True,
    )


def _format_today_summary(now_data: dict[str, Any], daily_data: dict[str, Any]) -> str:
    now = now_data.get("now") or {}
    today = (daily_data.get("daily") or [{}])[0] or {}
    parts = [
        "今天天气",
        f"当前{now.get('text', '未知')}，{now.get('temp', '?')}度，体感{now.get('feelsLike', '?')}度",
        f"今日{today.get('textDay', '未知')} / {today.get('textNight', '未知')}",
        f"气温{today.get('tempMin', '?')}度~{today.get('tempMax', '?')}度",
        f"湿度{now.get('humidity', '?')}%，风向{now.get('windDir', '未知')}，风速{now.get('windSpeed', '?')}",
    ]
    if today.get("precip"):
        parts.append(f"预计降水量{today.get('precip')}")
    return "；".join(parts) + "。"


def _format_alert_summary(alert_data: dict[str, Any]) -> str:
    alerts = alert_data.get("alerts") or []
    if not alerts:
        return "当前没有生效中的天气预警。"
    lines = [f"当前有 {len(alerts)} 条生效中的天气预警。"]
    for index, item in enumerate(alerts, 1):
        title = item.get("title") or item.get("typeName") or "天气预警"
        severity = item.get("severity") or item.get("severityColor") or "未知等级"
        end_time = item.get("endTime") or "未知结束时间"
        text = item.get("text") or ""
        lines.append(f"{index}. {title}（{severity}，至 {end_time}）：{text}")
    return "\n".join(lines)


def validate_settings(ctx):
    _required_settings(ctx)
    try:
        _build_jwt(
            str(_setting(ctx, "private_key_pem")).strip(),
            str(_setting(ctx, "project_id")).strip(),
            str(_setting(ctx, "key_id")).strip(),
            int(_setting(ctx, "jwt_ttl_seconds", 900) or 900),
        )
    except PluginUserVisibleError:
        raise
    except Exception as exc:
        return f"和风天气 JWT 生成失败: {exc}"
    return None


def daily_forecast(ctx):
    token, cfg = _token_and_config(ctx)
    try:
        now_data = _weather_now(cfg["api_host"], token, cfg)
        daily_data = _weather_daily(cfg["api_host"], token, cfg)
    except Exception as exc:
        raise PluginUserVisibleError(str(exc), user_id=ctx.user_id) from exc
    return {
        "summary": _format_today_summary(now_data, daily_data),
        "payload": {
            "kind": "qweather_daily_forecast",
            "weather_now": now_data,
            "weather_daily": daily_data,
        },
    }


def weather_alerts(ctx):
    token, cfg = _token_and_config(ctx)
    try:
        alert_data = _weather_alerts(cfg["api_host"], token, cfg)
    except Exception as exc:
        raise PluginUserVisibleError(str(exc), user_id=ctx.user_id) from exc
    return {
        "summary": _format_alert_summary(alert_data),
        "payload": {
            "kind": "qweather_alerts",
            "weather_alerts": alert_data,
        },
    }
