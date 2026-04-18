# ExternalContextService

源码：`backend/app/services/runtime/context/external_context_service.py`

## 功能

- 为 `wakeup`、`pull`、`merge` 这类事件补充外部上下文。
- 把 source cocoon 的消息、记忆和 merge 专用快照装进 `external_context`。

## 对外接口

- `build(session, event)`

## 交互方式

- 由 `ContextBuilder` 调用。
- 下游依赖 `MessageWindowService` 和 `MemoryService`。
