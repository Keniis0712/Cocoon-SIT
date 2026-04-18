# ArtifactStore

源码：`backend/app/services/storage/base.py`

## 功能

- 定义审计工件存储的统一抽象。
- 让上层 `AuditService` 不依赖具体文件系统或对象存储实现。

## 对外接口

- `write_text(relative_path, content)`
- `delete(relative_path)`

## 交互方式

- `AuditService` 只依赖这个抽象。
- 当前默认实现是 `FilesystemArtifactStore`，后续可以替换为 MinIO/S3。
