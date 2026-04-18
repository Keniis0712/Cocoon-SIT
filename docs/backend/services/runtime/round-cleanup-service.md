# RoundCleanupService

源码：`backend/app/services/runtime/round_cleanup.py`

## 功能

- 在编辑消息或重试回复前，删除受影响的后续消息、记忆、message tag、memory tag、失败轮次和关联审计数据。
- 保证“从某个点重跑”时上下文一致。

## 对外接口

- `cleanup_for_edit(session, cocoon_id, edited_message_id)`
- `cleanup_for_retry(session, cocoon_id, message_id=None)`

## 交互方式

- 上游由 `ChatRuntime` 在处理 `edit` / `retry` action 时调用。
- 下游直接操作 `messages/memory_chunks/audit_runs/audit_artifacts/failed_rounds`。
