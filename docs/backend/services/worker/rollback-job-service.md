# RollbackJobService

源码：`backend/app/worker/jobs/rollback_job_service.py`

## 功能

- 执行 checkpoint 回滚。
- 同步消息清理、checkpoint 激活状态和 session rollback 标记。

## 对外接口

- `execute(session, checkpoint_id)`
