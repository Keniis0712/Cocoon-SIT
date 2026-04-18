# RealtimeHub

源码：`backend/app/services/realtime/hub.py`

## 功能

- 统一封装“发布事件到 backplane”和“从 backplane 回流到本地 websocket”。
- 抹平调用方对事件来源的感知。

## 对外接口

- `start()`
- `stop()`
- `publish(cocoon_id, event)`
- `handle_backplane_event(cocoon_id, event)`

## 交互方式

- 上游主要是 API 路由、`ChatRuntime`、`WorkerRuntime`。
- 下游依赖 `RealtimeBackplane`、`ConnectionManager` 和 `EventDeliveryService`。
