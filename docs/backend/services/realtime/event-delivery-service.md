# EventDeliveryService

源码：`backend/app/services/realtime/event_delivery_service.py`

## 功能

- 根据当前是否有绑定 loop、是否处于 async 上下文，选择正确的本地广播调度方式。
- 把 loop 调度逻辑从 `RealtimeHub` 中拆开。

## 对外接口

- `deliver(manager, cocoon_id, event)`

## 交互方式

- 由 `RealtimeHub.handle_backplane_event()` 调用。
- 下游调用 `ConnectionManager.broadcast_local()`。
