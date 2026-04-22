# API Response Contracts

Source:
- `backend/app/api/routes/`
- `backend/app/schemas/`
- `packages/ts-sdk/`

## Purpose

- Defines one uniform HTTP response envelope for every REST API under `/api/v1`.
- Keeps existing HTTP status codes, while making frontend error handling depend on machine-readable `code`.
- Provides the contract that backend, OpenAPI, SDK, and frontend should all follow.

## Scope

- Applies to all HTTP routes under `/api/v1`.
- Does not apply to WebSocket frames.
- Does not change static frontend mount behavior outside `/api/v1`.

## Envelope Shape

Every successful or failed API response should use:

```json
{
  "code": "OK",
  "msg": "ok",
  "data": {}
}
```

Field rules:

- `code`
  - Stable machine-readable application code.
  - Frontend logic should branch on this field instead of parsing `msg`.
- `msg`
  - Human-readable message.
  - Safe to show in toast/dialog logs.
- `data`
  - Success payload for normal responses.
  - `null` or structured error metadata for failures.

## Success Contract

Success responses keep their current HTTP status codes and move the previous body into `data`.

Examples:

### `200 OK`

Old:

```json
{
  "id": "role_123",
  "name": "admin"
}
```

New:

```json
{
  "code": "OK",
  "msg": "ok",
  "data": {
    "id": "role_123",
    "name": "admin"
  }
}
```

### `202 Accepted`

Old:

```json
{
  "accepted": true,
  "action_id": "act_123",
  "status": "queued"
}
```

New:

```json
{
  "code": "ACCEPTED",
  "msg": "accepted",
  "data": {
    "accepted": true,
    "action_id": "act_123",
    "status": "queued"
  }
}
```

## Error Contract

Errors also use the same envelope while preserving the current HTTP status code.

### Business Error Example

Old:

HTTP `400`

```json
{
  "detail": "Invite quota exceeded"
}
```

New:

HTTP `400`

```json
{
  "code": "INVITE_QUOTA_EXCEEDED",
  "msg": "Invite quota exceeded",
  "data": null
}
```

### Validation Error Example

Old:

HTTP `422`

```json
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

New:

HTTP `422`

```json
{
  "code": "VALIDATION_ERROR",
  "msg": "Request validation failed",
  "data": {
    "errors": [
      {
        "loc": ["body", "name"],
        "msg": "Field required",
        "type": "missing"
      }
    ]
  }
}
```

## Code Rules

### Success Codes

- `OK`
  - Default for `200`
- `ACCEPTED`
  - Default for `202`

If the project later introduces `201` or `204`, the default codes should be:

- `CREATED`
- `NO_CONTENT`

### Error Codes

Error codes should be semantic and stable.

Priority:

1. Use a known explicit application code when available.
2. Otherwise derive a stable code from the business error message.
3. Fall back to a status-family code only when no message-specific code exists.

Examples:

- `AUTH_MISSING_BEARER`
- `AUTH_INVALID_CREDENTIALS`
- `AUTH_INVALID_TOKEN`
- `AUTH_INACTIVE_USER`
- `INVITE_NOT_FOUND`
- `INVITE_QUOTA_EXCEEDED`
- `GROUP_NOT_FOUND`
- `CHARACTER_ACCESS_DENIED`
- `VALIDATION_ERROR`
- `INTERNAL_SERVER_ERROR`

### Fallback Codes by Status

When a specific business code is unavailable:

- `400` -> `BAD_REQUEST`
- `401` -> `UNAUTHORIZED`
- `403` -> `FORBIDDEN`
- `404` -> `NOT_FOUND`
- `409` -> `CONFLICT`
- `422` -> `VALIDATION_ERROR`
- `500` -> `INTERNAL_SERVER_ERROR`
- `502` -> `BAD_GATEWAY`
- `503` -> `SERVICE_UNAVAILABLE`

## Data Rules

### Success

- `data` contains the existing response payload.
- Existing route response models become payload models inside the envelope.

Examples:

- `list[UserOut]`
- `TokenPair`
- `AcceptedResponse`
- `AuditRunDetail`

### Error

- Business/domain errors: `data = null`
- Validation errors: `data.errors = [...]`
- Future field-level business errors may use:

```json
{
  "code": "FORM_INVALID",
  "msg": "Form validation failed",
  "data": {
    "fields": {
      "username": ["Already exists"]
    }
  }
}
```

## OpenAPI / SDK Contract

The OpenAPI contract should describe the envelope, not the inner payload directly.

That means:

- `response_model=UserOut` becomes `response_model=ApiEnvelope[UserOut]`
- `response_model=list[UserOut]` becomes `response_model=ApiEnvelope[list[UserOut]]`
- SDK generated response types should expose `code`, `msg`, and `data`

Frontend API wrappers may still unwrap `data` for app-level convenience, but the transport contract must remain enveloped.

## Migration Plan

### Phase 1

- Add shared envelope schemas and response helpers.
- Add API exception handlers for:
  - `HTTPException`
  - `RequestValidationError`
  - unexpected server exceptions

### Phase 2

- Switch all REST routers to automatically wrap success responses.
- Preserve current HTTP status codes.
- Preserve current inner payload schema under `data`.

### Phase 3

- Regenerate OpenAPI and `packages/ts-sdk`.
- Update frontend API wrappers to consume enveloped transport responses.
- Update tests to assert envelope shape and machine-readable `code`.

## Testing Expectations

API and integration tests should check:

- HTTP status code remains unchanged
- `code` is stable
- `msg` stays human-readable
- `data` contains the old payload shape

Example:

```python
assert response.status_code == 400
payload = response.json()
assert payload["code"] == "INVITE_QUOTA_EXCEEDED"
assert payload["msg"] == "Invite quota exceeded"
assert payload["data"] is None
```

## Notes

- Frontend toast rendering should prefer `msg`, but business branching must use `code`.
- Backend services can keep raising `HTTPException(detail=...)` during the migration; the API layer should translate them into the unified envelope.
- This contract is intentionally transport-level. It does not require changing the internal service return types.
