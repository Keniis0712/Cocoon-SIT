# PromptAssemblyService

源码：`backend/app/services/runtime/generation/prompt_assembly_service.py`

## 功能

- 把 `system` 模板和事件模板组装成最终 prompt 栈。
- 同时给 `GeneratorNode` 返回 provider 侧需要的 `messages` 列表。

## 对外接口

- `build(session, context, provider_capabilities)`

## 交互方式

- 上游由 `GeneratorNode` 调用。
- 下游依赖 `PromptTemplateService` 和 runtime prompt helper。

## 子产物

- `RenderedPromptSegment`
- `PromptAssembly`

这两个结构分别描述单段 prompt 和完整组装结果，便于审计与测试。
