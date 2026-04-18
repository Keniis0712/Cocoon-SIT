# RoleService

源码：`backend/app/services/access/role_service.py`

## 功能

- 管理角色列表、创建和更新。
- 维护角色权限字典。

## 对外接口

- `list_roles(session)`
- `create_role(session, payload)`
- `update_role(session, role_id, payload)`
