# AuthorizationService

Source: `backend/app/services/security/authorization_service.py`

## Purpose

- Applies higher-level authorization rules on top of raw RBAC permission checks.
- Centralizes "who may act on which resource" decisions for access, workspace, and admin flows.

## Public Interface

- Resource and actor authorization helpers in `AuthorizationService`

## Notes

- `rbac.py` answers "which permissions does this user have?"
- `authorization_service.py` answers "may this actor perform this concrete action on this concrete resource?"
- Integration tests under `backend/tests/integration/test_authorization_service.py` exercise the main decision paths.
