# DurableJobService

源码：`backend/app/services/jobs/durable_jobs.py`

## 功能

- 管理 durable job 的入队、claim、完成状态变更。
- 支撑 wakeup、merge、pull、rollback、memory compaction、artifact cleanup 等异步任务。

## 对外接口

- `enqueue(session, job_type, lock_key, payload_json, cocoon_id=None, available_at=None)`
- `claim_next(session, worker_name)`
- `finish(session, job, status, error_text=None)`

## 交互方式

- 上游来自工作流 API 和 `SchedulerNode.schedule_wakeup()`。
- 下游由 `WorkerRuntime.process_next_durable_job()` claim，并交给 `DurableJobExecutor` 执行。

## 注意点

- `available_at` 允许未来任务延迟可见，wakeup 依赖这个字段避免提前执行。
