# MetaNode

源码：`backend/app/services/runtime/meta_node.py`

## 功能

- 负责 runtime 的“前置决策”阶段。
- 当前会渲染 `meta` 模板、记录审计工件，并产出 `MetaDecision`。

## 对外接口

- `evaluate(session, context, audit_run, audit_step)`

## 交互方式

- 上游由 `ChatRuntime` 调用。
- 下游依赖 `PromptTemplateService`、runtime prompt helper、`WakeupCommandParser`。

## 当前职责

- 判断是否 `silence`。
- 计算 `relation_delta`、`persona_patch`。
- 识别显式 `/wakeup` 指令并转成调度 hint。
