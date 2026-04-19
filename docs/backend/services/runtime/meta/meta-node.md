# MetaNode

源码：`backend/app/services/runtime/meta_node.py`

## 功能

- 负责每一轮 runtime 的前置决策。
- 通过 `meta` prompt + chat provider 获取结构化 JSON，而不是依赖自由文本或本地命令解析。
- 输出 `MetaDecision`，其中包含：
  - `decision`
  - `relation_delta`
  - `persona_patch`
  - `tag_ops`
  - `next_wakeup_hints`
  - `cancel_wakeup_task_ids`

## 结构化输出约束

- `MetaNode` 会给 provider 注入 `COCOON_META_OUTPUT_V1` 标记。
- provider 必须返回严格 JSON，对象字段固定。
- 每个新建 wakeup 都必须带 `reason`。
- 当当前事件是 idle wakeup 时，prompt 会明确鼓励 AI 在合适时机主动重新开启对话。

## 上下文

- `runtime_event`
- `session_state`
- `pending_wakeups`
- `wakeup_context`
- `now_utc`

其中 `pending_wakeups` 会携带现有 wakeup 的 `id / run_at / reason / status`，因此 AI 可以做“保留、追加、取消指定任务”的决策。

## 备注

- 旧的 `/wakeup` 文本指令解析路径已经移除。
- 如果 provider 没返回合法 JSON，会退回到本地 fallback 逻辑，避免整轮失败。
