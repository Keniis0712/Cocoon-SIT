# MessageDispatchService

源码：`backend/app/services/workspace/message_dispatch_service.py`

## 功能

- 负责消息相关 action 的编排式落库和入队。
- 把“写 ActionDispatch / 写 Message / 写 tag / 调 queue / 发 realtime 事件”从 router 中抽离。

## 对外接口

- `enqueue_chat_message(session, cocoon_id, content, client_request_id, timezone)`
- `enqueue_user_message_edit(session, cocoon_id, message, content)`
- `enqueue_retry(session, cocoon_id, message_id)`

## 交互方式

- 上游由 `workspace/messages.py` 调用。
- 下游依赖 `ChatDispatchQueue` 和 `RealtimeHub`。

## 注意点

- `enqueue_chat_message` 内部处理了 `client_request_id` 幂等。
