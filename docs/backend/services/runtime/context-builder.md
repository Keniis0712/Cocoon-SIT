# ContextBuilder

源码：`backend/app/services/runtime/context/builder.py`

## 功能

- 为当前 runtime 轮次组装 `ContextPackage`。
- 负责加载 cocoon、character、session_state、可见消息、记忆上下文以及外部上下文。

## 对外接口

- `build(session, event)`

## 交互方式

- 上游由 `ChatRuntime` 和部分 durable job 流程调用。
- 下游依赖 `MemoryService`、`MessageWindowService`、`ExternalContextService`。

## 注意点

- 如果 `SessionState` 不存在，会在这里懒创建。
