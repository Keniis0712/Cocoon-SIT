# RuntimeJobService

源码：`backend/app/worker/jobs/runtime_job_service.py`

## 功能

- 负责 `wakeup`、`pull`、`merge` 这三类 durable job 的 runtime 执行。
- 统一通过 `ChatRuntime` 跑业务轮次，并同步 job 侧状态。

## 对外接口

- `execute_wakeup(session, job)`
- `execute_pull(session, job)`
- `execute_merge(session, job)`
