# Backend API Structure

后端 API 入口在 `backend/app/api/router.py`，现在按功能域拆成 4 组 router。

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

## Workspace

目录：`backend/app/api/routes/workspace/`

- `cocoons.py`：cocoon 基础 CRUD、树、session state
- `messages.py`：消息列表、发送、编辑、重试
- `tags.py`：cocoon 标签绑定与查询
- `rollback.py`：checkpoint 回滚请求
- `realtime.py`：cocoon websocket
- `memory.py`：记忆查询与压缩
- `wakeup.py`：wakeup 入队和列表
- `pulls.py`：pull job
- `merges.py`：merge job
- `checkpoints.py`：checkpoint 管理

其中 `workspace` 这一组现在不再把所有行为塞进一个文件，而是按“实体操作 / 消息操作 / 标签操作 / 异步动作 / 实时连接”进一步细分。

## Observability

目录：`backend/app/api/routes/observability/`

- `health.py`：健康检查
- `audits.py`：审计查询，委托 `AuditQueryService`
- `insights.py`：汇总指标，委托 `InsightQueryService`
- `admin_artifacts.py`：审计 artifact 管理，委托 `ArtifactAdminService`

## 路由与服务的边界

当前约定是：

- router：参数校验、权限依赖、HTTP/WS 协议适配
- service：业务编排和跨模块协作
- runtime / jobs / providers 等底层服务：负责真正的领域逻辑与执行

现在 `observability` 这一组也已经从“路由里直接查库拼 dict”收成了“薄路由 + typed schema + application service”。

`workspace/messages.py`、`workspace/tags.py`、`workspace/realtime.py` 这些 router 已经开始改成“薄路由”，主要依赖：

- `MessageDispatchService`
- `CocoonTagService`
- `WorkspaceRealtimeService`

这也是后续继续细分 API 层时的推荐方向。
