"""Encryption helpers for provider secrets and password hashes."""

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet


def ensure_fernet_key(raw_key: str) -> bytes:
    encoded = raw_key.encode("utf-8")
    try:
        Fernet(encoded)
        return encoded
    except Exception:
        digest = hashlib.sha256(encoded).digest()
        return base64.urlsafe_b64encode(digest)


class SecretCipher:
    """Encrypts and decrypts provider secrets with a master key."""

    def __init__(self, master_key: str):
        self._fernet = Fernet(ensure_fernet_key(master_key))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")

    @staticmethod
    def mask_secret(secret: str) -> str:
        if len(secret) <= 8:
            return "*" * len(secret)
        return f"{secret[:4]}{'*' * (len(secret) - 8)}{secret[-4:]}"


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def verify_secret(secret: str, expected_hash: str) -> bool:
    actual = hash_secret(secret)
    return hmac.compare_digest(actual, expected_hash)
