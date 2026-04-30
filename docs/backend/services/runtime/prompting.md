# Runtime Prompting Helpers

源码：`backend/app/services/runtime/prompting/prompting.py`

## 功能

- 统一把 `ContextPackage` 转成 prompt 变量字典。
- 统一把 prompt 渲染过程产出成审计 artifact。

## 对外接口

- `build_runtime_prompt_variables(context, provider_capabilities=None)`
- `record_prompt_render_artifacts(session, audit_service, audit_run, audit_step, template, revision, snapshot, rendered_prompt, summary_prefix)`

## 交互方式

- `MetaNode`、`PromptAssemblyService`、`DurableJobExecutor` 都会复用这里。
- 下游是 `AuditService` 的 artifact 记录接口。
