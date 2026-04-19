# ChatRuntime

源码：`backend/app/services/runtime/chat_runtime.py`

## 功能

- 编排一轮完整 runtime：
  - cleanup
  - context build
  - meta decision
  - scheduler
  - generation
  - side effects
  - audit
  - realtime publish

## 当前语义

- `MetaNode` 和 `GeneratorNode` 都走结构化输出。
- scheduler 支持多 wakeup、指定取消、默认 idle wakeup。
- 最终 `state_patch` 会在 side effects 之后再次发布一次，确保前端拿到的是包含最新 wakeup 指针的状态。

## audit

- `meta_output` 会记录：
  - `decision`
  - `next_wakeup_hints`
  - `cancel_wakeup_task_ids`
- `generator_output` 会记录：
  - `content`
  - `structured_output`
- `workflow_summary` 会记录 scheduler 产出的 wakeup / cancellation 结果

## 适用范围

- 同时服务 `cocoon` 和 `chat_group`
- 同时服务普通聊天、wakeup、pull、merge 等 runtime 事件
