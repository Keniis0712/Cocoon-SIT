from __future__ import annotations

import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.requests import Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api.responses import (
    ApiEnvelopeMiddleware,
    _code_from_detail,
    _decode_json_body,
    _extract_detail,
    _is_openapi_envelope_schema,
    _message_from_detail,
    _normalize_code_token,
    _read_response_body,
    _wrap_openapi_api_responses,
    _wrap_openapi_operation,
    build_error_envelope,
    install_api_envelope_openapi,
    register_api_response_handlers,
)


def test_build_error_envelope_prefers_override_and_nested_messages():
    auth_error = build_error_envelope(status_code=401, detail="Invalid credentials")
    nested_error = build_error_envelope(status_code=400, detail={"detail": {"message": "too small"}})
    numeric_error = build_error_envelope(status_code=500, detail=123)

    assert auth_error == {
        "code": "AUTH_INVALID_CREDENTIALS",
        "msg": "Invalid credentials",
        "data": None,
    }
    assert nested_error == {
        "code": "TOO_SMALL",
        "msg": "too small",
        "data": None,
    }
    assert numeric_error == {
        "code": "123",
        "msg": "123",
        "data": None,
    }


def test_response_helpers_cover_decode_extract_and_code_fallbacks():
    assert _decode_json_body(b"") is None
    assert _decode_json_body(b'{"ok": true}') == {"ok": True}
    assert _extract_detail({"detail": {"msg": "nested"}}) == {"msg": "nested"}
    assert _extract_detail("plain") == "plain"
    assert _message_from_detail(["x"]) is None
    assert _message_from_detail({"msg": {"detail": "inner"}}) == "inner"
    assert _normalize_code_token("   ") == ""
    assert _code_from_detail(422, [{"loc": ["body"]}], "ignored") == "VALIDATION_ERROR"
    assert _code_from_detail(418, {}, "") == "INTERNAL_SERVER_ERROR"


@pytest.mark.anyio
async def test_read_response_body_supports_streaming_response():
    response = StreamingResponse(iter([b'{"x":', b"1}"]), media_type="application/json")

    body = await _read_response_body(response)

    assert json.loads(body) == {"x": 1}


def test_wrap_openapi_operation_handles_success_validation_and_skip_cases():
    operation = {
        "responses": {
            "200": {"content": {"application/json": {"schema": {"type": "object", "properties": {"value": {"type": "string"}}}}}},
            "204": {"content": {"application/json": {"schema": {"type": "object", "properties": {}}}}},
            "422": {"content": {"application/json": {"schema": {"type": "object"}}}},
            "500": {"content": {"text/plain": {"schema": {"type": "string"}}}},
            "201": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {"code": {"type": "string"}, "msg": {"type": "string"}, "data": {"type": "object"}},
                        }
                    }
                }
            },
        }
    }

    _wrap_openapi_operation(operation)

    success_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert success_schema["properties"]["code"]["example"] == "OK"
    assert success_schema["properties"]["data"]["properties"]["value"]["type"] == "string"
    assert operation["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ApiValidationEnvelope"
    }
    assert _is_openapi_envelope_schema(
        operation["responses"]["201"]["content"]["application/json"]["schema"]
    )
    assert "application/json" not in operation["responses"]["500"]["content"]


def test_wrap_openapi_api_responses_only_touches_api_paths_and_http_methods():
    schema = {
        "paths": {
            "/api/v1/items": {
                "get": {"responses": {"200": {"content": {"application/json": {"schema": {"type": "object"}}}}}},
                "trace": {"responses": {"200": {"content": {"application/json": {"schema": {"type": "object"}}}}}},
            },
            "/web/page": {
                "get": {"responses": {"200": {"content": {"application/json": {"schema": {"type": "object"}}}}}},
            },
        }
    }

    _wrap_openapi_api_responses(schema, "/api/v1")

    api_schema = schema["paths"]["/api/v1/items"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    web_schema = schema["paths"]["/web/page"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    trace_schema = schema["paths"]["/api/v1/items"]["trace"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert api_schema["properties"]["code"]["example"] == "OK"
    assert web_schema == {"type": "object"}
    assert trace_schema == {"type": "object"}
    assert "ApiValidationEnvelope" in schema["components"]["schemas"]


def test_install_api_envelope_openapi_caches_wrapped_schema():
    app = FastAPI()

    class Item(BaseModel):
        value: str

    @app.get("/api/v1/items", response_model=Item)
    def _get_item():
        return {"value": "ok"}

    install_api_envelope_openapi(app, "/api/v1")

    first = app.openapi()
    second = app.openapi()

    assert first is second
    wrapped = first["paths"]["/api/v1/items"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert wrapped["properties"]["data"]["$ref"] == "#/components/schemas/Item"


def test_register_api_response_handlers_wrap_api_errors_and_leave_non_api_routes_plain():
    app = FastAPI()
    register_api_response_handlers(app, "/api")

    @app.get("/api/ok")
    def _api_ok():
        return {"value": 1}

    @app.get("/api/http-error")
    def _api_http_error():
        raise HTTPException(status_code=404, detail="missing item")

    @app.get("/api/crash")
    def _api_crash():
        raise RuntimeError("boom")

    @app.get("/plain/http-error")
    def _plain_http_error():
        raise HTTPException(status_code=404, detail="plain missing")

    client = TestClient(app, raise_server_exceptions=False)

    ok = client.get("/api/ok")
    api_http_error = client.get("/api/http-error")
    api_crash = client.get("/api/crash")
    plain_http_error = client.get("/plain/http-error")

    assert ok.json() == {"value": 1}
    assert api_http_error.json() == {"code": "MISSING_ITEM", "msg": "missing item", "data": None}
    assert api_crash.json() == {"code": "INTERNAL_SERVER_ERROR", "msg": "Internal server error", "data": None}
    assert plain_http_error.json() == {"detail": "plain missing"}


@pytest.mark.anyio
async def test_api_envelope_middleware_wraps_success_and_skips_plain_text_and_existing_envelopes():
    app = FastAPI()
    middleware = ApiEnvelopeMiddleware(app, api_prefix="/api")

    async def _dispatch(path: str, response):
        async def _call_next(_):
            return response

        request = Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("utf-8"),
                "query_string": b"",
                "headers": [],
                "client": ("testclient", 50000),
                "server": ("testserver", 80),
                "root_path": "",
                "app": app,
            }
        )
        return await middleware.dispatch(request, _call_next)

    wrapped = await _dispatch("/api/ok", JSONResponse({"value": 2}, status_code=200, headers={"x-test": "1"}))
    existing = await _dispatch("/api/already", JSONResponse({"code": "OK", "msg": "ok", "data": {"value": 2}}))
    plain_text = await _dispatch("/api/plain-text", PlainTextResponse("hello"))
    non_api = await _dispatch("/plain/ok", JSONResponse({"value": 3}))

    assert json.loads(wrapped.body) == {"code": "OK", "msg": "ok", "data": {"value": 2}}
    assert wrapped.headers["x-test"] == "1"
    assert json.loads(existing.body) == {"code": "OK", "msg": "ok", "data": {"value": 2}}
    assert plain_text.body == b"hello"
    assert json.loads(non_api.body) == {"value": 3}
