# RuntimeActionService

源码：`backend/app/worker/jobs/runtime_action_service.py`

## 功能

- 为 durable job 触发的 runtime 轮次创建 `ActionDispatch`。
- 把“生成运行中 action”从主执行器中拆开。

## 对外接口

- `create_runtime_action(session, cocoon_id, event_type, payload_json)`
