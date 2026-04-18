# RealtimeBackplane Family

源码：`backend/app/services/realtime/backplane.py`

## 功能

- 抽象 WebSocket 事件在“本地连接管理器”和“跨进程/跨实例广播层”之间的桥接。
- 当前提供 `InMemoryRealtimeBackplane` 和 `RedisRealtimeBackplane`。

## 对外接口

- `publish(cocoon_id, event)`
- `subscribe(handler)`
- `start()`
- `stop()`

## 交互方式

- 上游由 `RealtimeHub.publish()` 调用。
- 下游把消息推给本地 handler；Redis 实现通过 pub/sub 广播。
