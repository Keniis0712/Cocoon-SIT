# CompactionJobService

源码：`backend/app/worker/jobs/compaction_job_service.py`

## 功能

- 执行 memory compaction durable job。
- 渲染 `memory_summary` 模板并调用 provider 生成摘要记忆。

## 对外接口

- `execute(session, cocoon_id, before_message_id=None)`
