# FilesystemArtifactStore

源码：`backend/app/services/storage/filesystem.py`

## 功能

- 将审计 artifact 写入本地文件系统。
- 负责创建目录、返回最终文件路径，以及在清理阶段删除文件。

## 对外接口

- `write_text(relative_path, content)`
- `delete(relative_path)`

## 交互方式

- 由 `AuditService` 调用。
- 在开发和测试环境中作为默认 artifact store。

## 注意点

- 删除逻辑对 Windows 的短暂文件占用做了重试，避免人工清理接口偶发失败。
