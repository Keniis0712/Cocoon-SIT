# ModelCatalogService

源码：`backend/app/services/catalog/model_catalog_service.py`

## 功能

- 管理可用模型目录。
- 负责模型列表、创建和更新。

## 对外接口

- `list_models(session)`
- `create_model(session, payload)`
- `update_model(session, model_id, payload)`

## 交互方式

- 上游由 `catalog/models.py` 调用。
- 下游读写 `available_models` 表。
