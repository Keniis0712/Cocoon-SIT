# PromptTemplateAdminService

源码：`backend/app/services/catalog/prompt_template_admin_service.py`

## 功能

- 适配 prompt 模板服务到管理端 API。
- 负责把 active revision 拼成管理视图对象。

## 对外接口

- `list_templates(session)`
- `upsert_template(session, template_type, payload, user)`
