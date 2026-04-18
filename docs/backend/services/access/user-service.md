# UserService

源码：`backend/app/services/access/user_service.py`

## 功能

- 管理用户列表、创建和更新。
- 负责密码哈希与用户状态变更。

## 对外接口

- `list_users(session)`
- `create_user(session, payload)`
- `update_user(session, user_id, payload)`
