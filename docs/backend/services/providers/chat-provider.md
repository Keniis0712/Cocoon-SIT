# ChatProvider Family

源码：`backend/app/services/providers/base.py`

## 功能

- 定义聊天 provider 的统一接口 `ChatProvider`。
- 提供默认 `MockChatProvider`，用于本地和测试环境的流式输出。

## 对外接口

- `ChatProvider.stream_text(prompt, messages, model_name, provider_config)`
- `MockChatProvider.stream_text(...)`

## 交互方式

- `ProviderRegistry` 负责选择具体实现。
- `GeneratorNode` 只依赖这个抽象，不关心 provider 是 mock 还是真实网关。
