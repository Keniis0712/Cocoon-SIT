from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_plugin_module():
    repo_root = Path(__file__).resolve().parents[5]
    module_path = repo_root / "plugins" / "external" / "qweather_daily_alert" / "main.py"
    spec = importlib.util.spec_from_file_location("test_qweather_daily_alert", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_weather_alerts_accepts_zero_result_response(monkeypatch):
    module = _load_plugin_module()
    ctx = SimpleNamespace(user_id="user-1")
    cfg = {
        "api_host": "api.example.com",
        "alert_latitude": "31.23",
        "alert_longitude": "121.47",
        "lang": "zh",
        "local_time": True,
    }

    monkeypatch.setattr(module, "_token_and_config", lambda _ctx: ("token-1", cfg))
    monkeypatch.setattr(
        module.requests,
        "get",
        lambda *args, **kwargs: _FakeResponse({"metadata": {"zeroResult": True}, "alerts": []}),
    )

    result = module.weather_alerts(ctx)

    assert "没有" in result["summary"]
    assert result["payload"]["kind"] == "qweather_alerts"
    assert result["payload"]["weather_alerts"]["alerts"] == []


def test_qweather_get_keeps_non_alert_calls_strict(monkeypatch):
    module = _load_plugin_module()
    monkeypatch.setattr(
        module.requests,
        "get",
        lambda *args, **kwargs: _FakeResponse({"metadata": {"zeroResult": True}, "alerts": []}),
    )

    with pytest.raises(RuntimeError, match="code=None"):
        module._qweather_get("api.example.com", "token-1", "/v7/weather/now")


def test_qweather_get_retries_timeout_before_succeeding(monkeypatch):
    module = _load_plugin_module()
    calls = {"count": 0}

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise module.requests.Timeout("timed out")
        return _FakeResponse({"code": "200", "now": {"text": "晴"}})

    monkeypatch.setattr(module.requests, "get", fake_get)
    monkeypatch.setattr(module.time, "sleep", lambda *_args, **_kwargs: None)

    result = module._qweather_get("api.example.com", "token-1", "/v7/weather/now")

    assert calls["count"] == 3
    assert result["code"] == "200"
