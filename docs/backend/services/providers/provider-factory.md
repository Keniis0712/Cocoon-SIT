# ProviderFactory

源码：`backend/app/services/providers/provider_factory.py`

## 功能

- 把 `provider.kind` 映射成具体 provider 实现。
- 将 provider 选择逻辑从 `ProviderRegistry` 中拆开。

## 对外接口

- `resolve_chat_provider(provider_kind)`

## 交互方式

- 由 `ProviderRegistry` 调用。
- 当前支持 `mock` 和 `openai_compatible`，未知类型回退到 `mock`。
