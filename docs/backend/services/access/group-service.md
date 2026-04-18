# GroupService

源码：`backend/app/services/access/group_service.py`

## 功能

- 管理用户组和组成员关系。

## 对外接口

- `list_groups(session)`
- `create_group(session, payload)`
- `list_group_members(session, group_id)`
- `add_group_member(session, group_id, payload)`
