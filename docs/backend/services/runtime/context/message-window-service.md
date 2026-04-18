# MessageWindowService

源码：`backend/app/services/runtime/context/message_window_service.py`

## 功能

- 查询当前 cocoon 最近一段对话窗口。
- 根据 active tags 对消息做可见性过滤。

## 对外接口

- `list_visible_messages(session, cocoon_id, max_context_messages, active_tags)`

## 交互方式

- `ContextBuilder` 和 `ExternalContextService` 都通过它读取消息窗口。
- 下游读取 `messages` 和 `message_tags`。
