# ProviderService

源码：`backend/app/services/catalog/provider_service.py`

## 功能

- 管理模型 provider 的列表、创建和更新。
- 把 provider 基础 CRUD 从 router 中抽离。

## 对外接口

- `list_providers(session)`
- `create_provider(session, payload)`
- `update_provider(session, provider_id, payload)`

## 交互方式

- 上游由 `catalog/providers.py` 调用。
- 下游读写 `model_providers` 表。
