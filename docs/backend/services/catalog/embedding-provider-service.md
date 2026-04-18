# EmbeddingProviderService

源码：`backend/app/services/catalog/embedding_provider_service.py`

## 功能

- 管理 embedding provider 目录。
- 负责列表、创建和更新。

## 对外接口

- `list_embedding_providers(session)`
- `create_embedding_provider(session, payload)`
- `update_embedding_provider(session, embedding_provider_id, payload)`

## 交互方式

- 上游由 `catalog/embedding_providers.py` 调用。
- 下游读写 `embedding_providers` 表。
