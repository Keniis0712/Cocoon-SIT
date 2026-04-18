# SideEffects

源码：`backend/app/services/runtime/side_effects.py`

## 功能

- 将 meta 决策变成持久化状态变更。
- 将生成结果落为 message、memory，以及 action/audit 的完成态。

## 对外接口

- `apply_state_patch(session, context, meta)`
- `persist_generated_output(session, context, action, generation)`
- `finish_action(session, action, audit_run, status, error_text=None)`

## 交互方式

- 上游由 `ChatRuntime` 调用。
- 下游写 `session_states/messages/message_tags/memory_chunks/memory_tags/action_dispatches`。
