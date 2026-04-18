# ProviderCredentialService

源码：`backend/app/services/catalog/provider_credential_service.py`

## 功能

- 管理 provider credential 的创建、更新和读取。
- 负责 secret 的加密存储和 masked 回显。

## 对外接口

- `set_credential(session, provider_id, payload)`
- `get_credential(session, provider_id)`

## 交互方式

- 上游由 `catalog/provider_credentials.py` 调用。
- 依赖 `SecretCipher`、`ProviderCredential` 表。
