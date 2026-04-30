# Backend API Structure

后端入口位于 `backend/app/api/router.py`，当前按领域拆成 5 组 router。

## Access

目录：`backend/app/api/routes/access/`

- `auth.py`：登录、刷新、登出、当前用户
- `users.py`：用户管理
- `roles.py`：角色管理
- `groups.py`：用户组和成员关系
- `invites.py`：邀请码与兑换

## Catalog

目录：`backend/app/api/routes/catalog/`

- `characters.py`：角色设定与 ACL
- `providers.py`：provider 基础 CRUD
- `provider_credentials.py`：provider credential
- `models.py`：可用模型目录
- `embedding_providers.py`：embedding provider 目录
- `tags.py`：标签注册
- `prompt_templates.py`：prompt 模板管理
- `settings.py`：系统设置

## Workspace

目录：`backend/app/api/routes/workspace/`

- `cocoons.py`：cocoon CRUD、树、session state
- `chat_groups.py`：chat-group room CRUD、成员、消息、撤回、state、realtime
- `chat_group_tags.py`：chat-group 标签绑定与查询
- `messages.py`：cocoon 消息列表与发送
- `tags.py`：cocoon 标签绑定与查询
- `rollback.py`：checkpoint 回滚请求
- `realtime.py`：cocoon websocket
- `memory.py`：记忆查询与压缩
- `plugins.py`：工作区插件列表、启停、校验与绑定能力
- `pulls.py`：pull job
- `merges.py`：merge job
- `checkpoints.py`：checkpoint 管理

备注：

- 公开的 `/wakeup` API 已移除。
- wakeup 现在只走 runtime 内部调度，不再允许前端或用户命令直接创建。

## Observability

目录：`backend/app/api/routes/observability/`

- `health.py`：健康检查
- `audits.py`：审计查询
- `wakeups.py`：wakeup 查询与筛选
- `insights.py`：汇总指标
- `admin_artifacts.py`：artifact 管理

## Admin

目录：`backend/app/api/routes/admin/`

- `plugins.py`：插件安装、升级、全局配置、事件配置、共享依赖仓库

## Router 和 Service 的边界

- router：参数校验、权限依赖、HTTP/WS 协议适配
- service：业务编排和跨模块协作
- runtime / jobs / providers：底层执行逻辑
