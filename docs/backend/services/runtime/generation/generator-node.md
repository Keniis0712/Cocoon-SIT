# GeneratorNode

源码：`backend/app/services/runtime/generator_node.py`

## 功能

- 在 meta 决策允许回复时，执行真正的模型生成。
- 负责解析 provider、记录 prompt 审计、流式收集 chunks，并产出 `GenerationOutput`。

## 对外接口

- `generate(session, context, audit_run, audit_step)`

## 交互方式

- 上游由 `ChatRuntime` 调用。
- 下游依赖 `ProviderRegistry`、`PromptAssemblyService`、`AuditService` 和具体 `ChatProvider`。
