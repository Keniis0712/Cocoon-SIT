# ProviderRegistry

源码：`backend/app/services/providers/registry.py`

## 功能

- 作为 provider 解析总入口，对外暴露统一的 `resolve_chat_provider`。
- 自己不再直接承担全部逻辑，而是编排 `ModelSelectionService`、`ProviderRuntimeConfigService`、`ProviderFactory`。

## 对外接口

- `resolve_chat_provider(session, model_id)`

## 交互方式

- 上游由 `GeneratorNode` 和 `DurableJobExecutor` 使用。
- 下游会返回 provider 实例、model 记录、provider 记录和运行时配置字典。

## 当前子职责分配

- `ModelSelectionService`：解析 model/provider 记录。
- `ProviderRuntimeConfigService`：构建运行时配置并解密 credential。
- `ProviderFactory`：根据 `provider.kind` 选择具体实现。
