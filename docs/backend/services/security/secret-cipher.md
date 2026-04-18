# SecretCipher

源码：`backend/app/services/security/encryption.py`

## 功能

- 用 Fernet 主密钥对 provider secret 做加解密。
- 同时提供 secret mask、hash、verify 辅助能力。

## 对外接口

- `SecretCipher.encrypt(plaintext)`
- `SecretCipher.decrypt(ciphertext)`
- `SecretCipher.mask_secret(secret)`
- `ensure_fernet_key(raw_key)`
- `hash_secret(secret)`
- `verify_secret(secret, expected_hash)`

## 交互方式

- `ProviderRegistry` 用它解密 provider credential。
- provider 管理 API 在写密钥时使用加密和 mask。
