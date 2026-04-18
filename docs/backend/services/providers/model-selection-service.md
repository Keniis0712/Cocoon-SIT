# ModelSelectionService

源码：`backend/app/services/providers/model_selection_service.py`

## 功能

- 根据 `model_id` 读取聊天所需的 `AvailableModel` 与 `ModelProvider`。
- 把“模型存在性检查”和“provider 归属检查”从 `ProviderRegistry` 中拆出来。

## 对外接口

- `resolve_chat_model(session, model_id)`

## 交互方式

- 由 `ProviderRegistry` 调用。
- 下游只读 `available_models` 和 `model_providers`。
