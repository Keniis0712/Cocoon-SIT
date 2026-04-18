# ProviderRuntimeConfigService

源码：`backend/app/services/providers/provider_runtime_config_service.py`

## 功能

- 组装 provider 真正运行时使用的配置字典。
- 合并 model config、provider base_url 和解密后的 credential。

## 对外接口

- `build_chat_config(session, provider, model)`

## 交互方式

- 由 `ProviderRegistry` 调用。
- 依赖 `SecretCipher` 解密 `ProviderCredential`。
