# System Settings

源代码：
- `backend/app/models/system.py`
- `backend/app/services/catalog/system_settings_service.py`
- `backend/app/api/routes/catalog/settings.py`
- `backend/app/api/routes/access/auth.py`
- `frontend/src/api/settings.ts`
- `frontend/src/pages/Settings.tsx`

## 功能

- 提供单例系统配置，持久化在 `system_settings` 表。
- 提供后台可编辑的系统设置页面。
- 将公开特性接口和登录注册页联动到真实后端配置。

## 字段

- `allow_registration`
- `max_chat_turns`
- `allowed_model_ids`
- `default_cocoon_temperature`
- `default_max_context_messages`
- `default_auto_compaction_enabled`
- `private_chat_debounce_seconds`
- `rollback_retention_days`
- `rollback_cleanup_interval_hours`

## 对外接口

- `GET /api/v1/settings`
- `PUT /api/v1/settings`
- `GET /api/v1/auth/features`
- `POST /api/v1/auth/register`

## 运行时影响

- `allow_registration` 控制登录页是否展示注册入口，并由后端在注册时强校验。
- `allowed_model_ids` 为非空时，创建和更新 Cocoon 只能选择白名单模型。
- `default_cocoon_*` 在新建 Cocoon 且请求未显式覆盖时作为默认值。
- `private_chat_debounce_seconds` 控制 `chat/edit/retry` 的防抖窗口。
