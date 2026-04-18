# SchedulerNode

源码：`backend/app/services/runtime/scheduler_node.py`

## 功能

- 根据 meta 决策里的 `next_wakeup_hint` 安排下一次 wakeup。
- 同时维护 `SessionState.current_wakeup_task_id` 和对应 durable job 的一致性。

## 对外接口

- `schedule(session, context, meta)`
- `schedule_wakeup(session, cocoon_id, run_at, reason, payload_json=None)`

## 交互方式

- 上游来自 `ChatRuntime` 和 `/wakeup` API。
- 下游依赖 `DurableJobService`，并写 `WakeupTask` / `DurableJob` / `SessionState`。

## 注意点

- 已排队的 wakeup 会被复用和改期，而不是无限新增。
