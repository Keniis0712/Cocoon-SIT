# ArtifactCleanupJobService

源码：`backend/app/worker/jobs/artifact_cleanup_job_service.py`

## 功能

- 清理指定的 audit artifact，或执行 TTL 过期清理。

## 对外接口

- `execute(session, artifact_ids=None)`
