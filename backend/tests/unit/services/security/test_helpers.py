from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.services.security.encryption import (
    SecretCipher,
    ensure_fernet_key,
    hash_secret,
    verify_secret,
)
from app.services.security.rbac import list_permissions_for_user, require_permission
from app.services.security.token_service import TokenService


def test_ensure_fernet_key_accepts_valid_key_and_derives_invalid_key():
    valid_key = Settings().provider_master_key

    assert ensure_fernet_key(valid_key) == valid_key.encode("utf-8")
    assert ensure_fernet_key("short-key") != b"short-key"


def test_secret_cipher_round_trips_and_masks_secret():
    cipher = SecretCipher("unit-test-master-key")
    encrypted = cipher.encrypt("super-secret")

    assert cipher.decrypt(encrypted) == "super-secret"
    assert SecretCipher.mask_secret("short") == "*****"
    assert SecretCipher.mask_secret("1234567890") == "1234**7890"


def test_hash_and_verify_secret():
    digest = hash_secret("abc123")

    assert verify_secret("abc123", digest) is True
    assert verify_secret("wrong", digest) is False


def test_token_service_creates_and_decodes_access_and_refresh_tokens():
    settings = Settings(secret_key="unit-secret-key-for-tests-at-least-32-bytes")
    service = TokenService(settings)

    access = service.create_access_token("user-1")
    refresh = service.create_refresh_token("user-1")
    access_payload = service.decode_token(access)
    refresh_payload = service.decode_token(refresh)

    assert access_payload["sub"] == "user-1"
    assert refresh_payload["sub"] == "user-1"
    assert refresh_payload["typ"] == "refresh"
    assert access_payload["jti"] != refresh_payload["jti"]

    with pytest.raises(jwt.InvalidTokenError):
        TokenService(Settings(secret_key="different-key-for-tests-at-least-32-bytes")).decode_token(access)


def test_rbac_helpers_list_permissions_and_raise_when_missing():
    role = SimpleNamespace(permissions_json={"read": True, "write": False, "admin": True})
    session = SimpleNamespace(get=lambda model, role_id: role if role_id == "role-1" else None)
    user_with_role = SimpleNamespace(role_id="role-1")
    user_without_role = SimpleNamespace(role_id=None)
    user_missing_role = SimpleNamespace(role_id="missing")

    assert list_permissions_for_user(session, user_with_role) == {"read", "admin"}
    assert list_permissions_for_user(session, user_without_role) == set()
    assert list_permissions_for_user(session, user_missing_role) == set()

    require_permission(session, user_with_role, "read")

    with pytest.raises(HTTPException, match="Missing permission: write"):
        require_permission(session, user_with_role, "write")
