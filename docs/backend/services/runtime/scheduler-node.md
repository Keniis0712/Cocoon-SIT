# SchedulerNode

源码：`backend/app/services/runtime/scheduler_node.py`

## 功能

- 消费 `MetaDecision` 里的 wakeup 相关决策。
- 支持一次创建多个 wakeup。
- 支持取消指定 pending wakeup。
- 在用户没有显式安排 follow-up 时，自动补一个 idle wakeup。

## 自动 idle wakeup 规则

- 仅在 `chat` 事件后执行。
- 仅在本轮 `meta` 没有返回新的 wakeup，且当前 target 没有其他 pending wakeup 时补默认任务。
- 默认延迟：
  - 普通情况：5 分钟
  - `cocoon` 高频对话：2 分钟

当前“高频对话”判定优先参考：
- `recent_turn_count >= 3`
- `idle_seconds <= 120`
- 如果客户端没上传这些字段，再回退到最近消息窗口做近似判断

## wakeup payload

自动 idle wakeup 会写入：

- `trigger_kind = idle_timeout`
- `source_action_id`
- `source_event_type`
- `silence_started_at`
- `silence_delay_seconds`
- `silence_deadline_at`
- `idle_summary`
- `memory_owner_user_id`

`reason` 始终必填，并在真正执行 wakeup 时原样带回 runtime。

## SessionState 指针

- `SessionState.current_wakeup_task_id` 只表示“当前最早的 pending wakeup”。
- 即使系统里存在多个 wakeup，也只暴露一个当前指针给实时状态和前端。

## 取消语义

- 用户新发消息时，会优先取消同一 target 下的 idle-timeout wakeup。
- `MetaNode` 也可以通过 `cancel_wakeup_task_ids` 取消指定任务。
- 被取消的任务和 durable job 会标记为 `cancelled`，不会再被 worker claim。
