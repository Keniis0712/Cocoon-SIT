# ChatRuntime

源码：`backend/app/services/runtime/chat_runtime.py`

## 功能

- 编排一次聊天动作从“清理旧状态”到“构建上下文、meta 决策、生成回复、调度 follow-up、关闭 action”的完整链路。
- 是后端 runtime 层的总 orchestrator。

## 对外接口

- `run(session, action)`

## 交互方式

- 上游由 `WorkerRuntime.process_next_chat_dispatch()` 调用。
- 下游串联 `RoundCleanupService`、`ContextBuilder`、`MetaNode`、`GeneratorNode`、`SideEffects`、`SchedulerNode`、`AuditService`、`RealtimeHub`。

## 注意点

- 这里不直接写 provider 或队列，而是只负责 orchestration。
