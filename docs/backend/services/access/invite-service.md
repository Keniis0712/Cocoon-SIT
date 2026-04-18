# InviteService

源码：`backend/app/services/access/invite_service.py`

## 功能

- 管理邀请码与 quota 兑换。
- 负责过期检查和配额上限检查。

## 对外接口

- `list_invites(session)`
- `create_invite(session, payload, user)`
- `redeem_invite(session, code, payload)`
