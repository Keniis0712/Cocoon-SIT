# CharacterService

源码：`backend/app/services/catalog/character_service.py`

## 功能

- 管理角色设定及 ACL。

## 对外接口

- `list_characters(session)`
- `create_character(session, payload, user)`
- `update_character(session, character_id, payload)`
- `list_acl(session, character_id)`
- `create_acl(session, character_id, payload)`
