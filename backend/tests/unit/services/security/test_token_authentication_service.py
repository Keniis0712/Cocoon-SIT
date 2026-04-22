from types import SimpleNamespace

import pytest
from fastapi import HTTPException, WebSocketException

from app.services.security.token_authentication_service import TokenAuthenticationService


def test_token_authentication_service_resolves_active_user():
    token_service = SimpleNamespace(decode_token=lambda token: {"sub": "user-1"})
    session = SimpleNamespace(get=lambda model, key: SimpleNamespace(id="user-1", is_active=True))
    service = TokenAuthenticationService(token_service)

    user = service.resolve_active_user(session, "token")

    assert user.id == "user-1"


def test_token_authentication_service_rejects_invalid_or_inactive_user():
    service = TokenAuthenticationService(SimpleNamespace(decode_token=lambda token: (_ for _ in ()).throw(ValueError("bad"))))
    session = SimpleNamespace(get=lambda model, key: None)

    with pytest.raises(HTTPException, match="Invalid token"):
        service.resolve_active_user(session, "token")

    service_missing_sub = TokenAuthenticationService(SimpleNamespace(decode_token=lambda token: {}))
    with pytest.raises(HTTPException, match="Invalid token"):
        service_missing_sub.resolve_active_user(session, "token")

    service_inactive = TokenAuthenticationService(SimpleNamespace(decode_token=lambda token: {"sub": "user-1"}))
    inactive_session = SimpleNamespace(get=lambda model, key: SimpleNamespace(id="user-1", is_active=False))
    with pytest.raises(HTTPException, match="Inactive user"):
        service_inactive.resolve_active_user(inactive_session, "token")


def test_token_authentication_service_wraps_websocket_errors_and_checks_permissions(monkeypatch):
    token_service = SimpleNamespace(decode_token=lambda token: {"sub": "user-1"})
    session = SimpleNamespace(get=lambda model, key: SimpleNamespace(id="user-1", is_active=True))
    service = TokenAuthenticationService(token_service)
    user = service.resolve_active_websocket_user(session, "token")

    assert user.id == "user-1"

    failing = TokenAuthenticationService(SimpleNamespace(decode_token=lambda token: (_ for _ in ()).throw(ValueError("bad"))))
    with pytest.raises(WebSocketException, match="Invalid token"):
        failing.resolve_active_websocket_user(session, "token")

    called = []
    monkeypatch.setattr(
        "app.services.security.token_authentication_service.require_permission",
        lambda session, user, permission: called.append((user.id, permission)),
    )
    assert service.require_user_permission(session, user, "read") is user
    assert called == [("user-1", "read")]
