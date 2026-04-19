# ChatProvider Family

源码：`backend/app/services/providers/base.py`

## 功能

- 定义聊天 provider 的统一接口 `ChatProvider`。
- 提供 `MockChatProvider`，用于测试或显式配置的 mock 聊天模型。

## 对外接口

- `ChatProvider.generate_text(prompt, messages, model_name, provider_config)`
- `MockChatProvider.generate_text(...)`

## 交互方式

- `ProviderRegistry` 负责选择具体实现。
- `GeneratorNode` 只依赖这个抽象，不关心 provider 是 mock 还是真实网关。
- 启动 bootstrap 不再自动写入内置 mock provider；如果要使用 mock，需要显式创建对应 provider/model 记录。
