# InviteService

源码：`backend/app/services/access/invite_service.py`

## 职责

`InviteService` 现在不只负责“创建邀请码 + 兑换额度”，还负责一套完整的邀请码管理流：

- 列出邀请码
- 创建邀请码
- 撤销未使用的邀请码
- 列出额度下发记录
- 创建用户或用户组额度 grant
- 计算用户/用户组的当前额度摘要
- 兑换邀请码并写入 grant 记录

## 当前语义

### 1. 邀请码来源

`InviteCode` 现在显式记录：

- `created_by_user_id`
- `created_for_user_id`
- `source_type`
- `source_id`
- `revoked_at`

其中：

- `source_type="USER"` 表示从某个用户额度桶消费
- `source_type="GROUP"` 表示从某个用户组额度桶消费
- `source_type="ADMIN_OVERRIDE"` 表示管理员直接创建，不检查额度桶

### 2. 额度 grant

`InviteQuotaGrant` 现在显式记录：

- `granted_by_user_id`
- `source_type`
- `source_id`
- `target_type`
- `target_id`
- `quota`
- `is_unlimited`
- `note`

当前实现里，管理台 grant 默认由管理员以 `ADMIN_OVERRIDE` 方式发放。

### 3. 摘要计算

`get_summary(session, target_type, target_id)` 的语义是：

- 先汇总该目标收到的 grant
- 再扣掉该目标作为 source 创建、且尚未撤销的邀请码消耗
- 如果存在 `is_unlimited=true` 的 grant，则该目标视为无限额度

### 4. 撤销规则

只有“尚未使用”的邀请码可以撤销：

- `revoked_at is None`
- `quota_used == 0`

撤销后不会直接修改 grant 记录，摘要会通过“忽略已撤销的邀请码消耗”自动体现返还效果。

## 对外方法

- `list_invites(session)`
- `list_grants(session)`
- `create_invite(session, payload, user)`
- `revoke_invite(session, code)`
- `create_grant(session, payload, user)`
- `get_summary(session, target_type, target_id)`
- `redeem_invite(session, code, payload)`
