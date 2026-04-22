from __future__ import annotations

import json
import re
from copy import deepcopy
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import (
    http_exception_handler as default_http_exception_handler,
    request_validation_exception_handler as default_request_validation_exception_handler,
)
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware


_SUCCESS_CODES = {
    200: ("OK", "ok"),
    201: ("CREATED", "created"),
    202: ("ACCEPTED", "accepted"),
    204: ("NO_CONTENT", "no content"),
}

_FALLBACK_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_SERVER_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
}

_ERROR_CODE_OVERRIDES = {
    "Missing bearer token": "AUTH_MISSING_BEARER",
    "Invalid credentials": "AUTH_INVALID_CREDENTIALS",
    "Invalid refresh token": "AUTH_INVALID_REFRESH_TOKEN",
    "Unknown refresh token": "AUTH_UNKNOWN_REFRESH_TOKEN",
    "Invalid token": "AUTH_INVALID_TOKEN",
    "Inactive user": "AUTH_INACTIVE_USER",
    "User account is inactive": "AUTH_USER_INACTIVE",
    "Registration is unavailable": "AUTH_REGISTRATION_UNAVAILABLE",
    "Registration is disabled": "AUTH_REGISTRATION_DISABLED",
    "Invite quota exceeded": "INVITE_QUOTA_EXCEEDED",
}


def build_success_envelope(status_code: int, data: Any) -> dict[str, Any]:
    code, msg = _SUCCESS_CODES.get(status_code, ("OK", "ok"))
    return {"code": code, "msg": msg, "data": data}


def build_error_envelope(
    status_code: int,
    *,
    detail: Any,
    code: str | None = None,
    msg: str | None = None,
    data: Any = None,
) -> dict[str, Any]:
    resolved_msg = msg or _message_from_detail(detail) or _default_error_message(status_code)
    resolved_code = code or _code_from_detail(status_code, detail, resolved_msg)
    return {"code": resolved_code, "msg": resolved_msg, "data": data}


def is_api_envelope(payload: Any) -> bool:
    return isinstance(payload, dict) and {"code", "msg", "data"} <= set(payload.keys())


def register_api_response_handlers(app: FastAPI, api_prefix: str) -> None:
    app.add_middleware(ApiEnvelopeMiddleware, api_prefix=api_prefix)
    install_api_envelope_openapi(app, api_prefix)

    @app.exception_handler(HTTPException)
    async def api_http_exception_handler(request: Request, exc: HTTPException) -> Response:
        if not _is_api_request(request, api_prefix):
            return await default_http_exception_handler(request, exc)
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_envelope(status_code=exc.status_code, detail=exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def api_validation_exception_handler(request: Request, exc: RequestValidationError) -> Response:
        if not _is_api_request(request, api_prefix):
            return await default_request_validation_exception_handler(request, exc)
        return JSONResponse(
            status_code=422,
            content=build_error_envelope(
                status_code=422,
                detail="Request validation failed",
                code="VALIDATION_ERROR",
                msg="Request validation failed",
                data={"errors": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def api_unhandled_exception_handler(request: Request, exc: Exception) -> Response:
        if not _is_api_request(request, api_prefix):
            raise exc
        return JSONResponse(
            status_code=500,
            content=build_error_envelope(
                status_code=500,
                detail="Internal server error",
                code="INTERNAL_SERVER_ERROR",
                msg="Internal server error",
            ),
        )


class ApiEnvelopeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, api_prefix: str):
        super().__init__(app)
        self.api_prefix = api_prefix

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if not _is_api_request(request, self.api_prefix):
            return response
        if not _is_json_response(response):
            return response

        body = await _read_response_body(response)
        payload = _decode_json_body(body)
        if is_api_envelope(payload):
            return _rebuild_json_response(response, payload)
        if response.status_code >= 400:
            return _rebuild_json_response(
                response,
                build_error_envelope(
                    status_code=response.status_code,
                    detail=_extract_detail(payload),
                ),
            )
        return _rebuild_json_response(
            response,
            build_success_envelope(status_code=response.status_code, data=payload),
        )


async def _read_response_body(response: Response) -> bytes:
    body = getattr(response, "body", None)
    if body is not None:
        return body

    chunks: list[bytes] = []
    async for chunk in response.body_iterator:  # type: ignore[attr-defined]
        chunks.append(chunk)
    return b"".join(chunks)


def _rebuild_json_response(response: Response, payload: Any) -> JSONResponse:
    headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in {"content-length", "content-type"}
    }
    return JSONResponse(
        status_code=response.status_code,
        content=payload,
        headers=headers,
        background=response.background,
    )


def _decode_json_body(body: bytes) -> Any:
    if not body:
        return None
    return json.loads(body)


def _is_api_request(request: Request, api_prefix: str) -> bool:
    return request.scope.get("type") == "http" and request.url.path.startswith(api_prefix)


def _is_json_response(response: Response) -> bool:
    content_type = response.headers.get("content-type", "")
    return "application/json" in content_type.lower()


def _message_from_detail(detail: Any) -> str | None:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        nested_msg = detail.get("msg") or detail.get("message") or detail.get("detail")
        return _message_from_detail(nested_msg)
    if isinstance(detail, list):
        return None
    return str(detail) if detail is not None else None


def _code_from_detail(status_code: int, detail: Any, message: str) -> str:
    if isinstance(detail, list):
        return "VALIDATION_ERROR"
    if isinstance(detail, str) and detail in _ERROR_CODE_OVERRIDES:
        return _ERROR_CODE_OVERRIDES[detail]

    derived = _normalize_code_token(message)
    if derived:
        return derived
    return _FALLBACK_ERROR_CODES.get(status_code, "INTERNAL_SERVER_ERROR")


def _normalize_code_token(message: str) -> str:
    token = re.sub(r"[^A-Z0-9]+", "_", message.upper()).strip("_")
    if not token:
        return ""
    return token[:96]


def _default_error_message(status_code: int) -> str:
    return _FALLBACK_ERROR_CODES.get(status_code, "INTERNAL_SERVER_ERROR").replace("_", " ").title()


def _extract_detail(payload: Any) -> Any:
    if isinstance(payload, dict) and "detail" in payload:
        return payload["detail"]
    return payload


def install_api_envelope_openapi(app: FastAPI, api_prefix: str) -> None:
    default_openapi = app.openapi

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = deepcopy(default_openapi())
        _wrap_openapi_api_responses(schema, api_prefix)
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi


def _wrap_openapi_api_responses(openapi_schema: dict[str, Any], api_prefix: str) -> None:
    components = openapi_schema.setdefault("components", {}).setdefault("schemas", {})
    components.setdefault(
        "ApiValidationErrorData",
        {
            "type": "object",
            "required": ["errors"],
            "properties": {
                "errors": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/ValidationError"},
                }
            },
        },
    )
    components.setdefault(
        "ApiValidationEnvelope",
        {
            "type": "object",
            "required": ["code", "msg", "data"],
            "properties": {
                "code": {"type": "string", "example": "VALIDATION_ERROR"},
                "msg": {"type": "string", "example": "Request validation failed"},
                "data": {"$ref": "#/components/schemas/ApiValidationErrorData"},
            },
        },
    )

    for path, path_item in openapi_schema.get("paths", {}).items():
        if not path.startswith(api_prefix):
            continue
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            _wrap_openapi_operation(operation)


def _wrap_openapi_operation(operation: dict[str, Any]) -> None:
    for status_code, response in operation.get("responses", {}).items():
        content = response.get("content", {})
        json_content = content.get("application/json")
        if not json_content:
            continue
        schema = json_content.get("schema")
        if not schema:
            continue
        if _is_openapi_envelope_schema(schema):
            continue
        if status_code == "422":
            json_content["schema"] = {"$ref": "#/components/schemas/ApiValidationEnvelope"}
            continue

        success_code, success_msg = _SUCCESS_CODES.get(int(status_code), ("OK", "ok"))
        json_content["schema"] = {
            "type": "object",
            "required": ["code", "msg", "data"],
            "properties": {
                "code": {"type": "string", "example": success_code},
                "msg": {"type": "string", "example": success_msg},
                "data": deepcopy(schema),
            },
        }


def _is_openapi_envelope_schema(schema: dict[str, Any]) -> bool:
    properties = schema.get("properties")
    return isinstance(properties, dict) and {"code", "msg", "data"} <= set(properties.keys())
