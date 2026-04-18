# Cocoon-SIT Monorepo 后端实施方案（完整平台 v1）

## Summary

基于现有前后端文档，仓库按单仓模式规划为 `backend + frontend + packages/ts-sdk + deploy + docs`。  
后端采用 `Python/FastAPI + SQLAlchemy 2 + Alembic + Postgres + Redis + pgvector`，部署形态为 `API 单体 + 独立 Worker`。  
系统坚持 `REST 202 + 单 WebSocket` 统一协议，但任务分为两类：

- 短时对话类 `chat/edit/retry`：实际 dispatch 走 Redis，数据库保留最小 action 账本。
- 耐久任务类 `pull/merge/wakeup/rollback/compaction/audit cleanup`：任务真相源落 Postgres，Worker 从库里 claim。

Prompt 模板提升为正式配置能力：模板全局管理、立即生效、占位符渲染、保存渲染快照进入审计链。角色信息不是模板本身，而是模板变量输入的一部分。

## Implementation Changes

### 1. 仓库与目录

根目录采用 Monorepo：

- `backend/`
  - `app/api/` REST 与 WebSocket 路由、依赖注入、鉴权
  - `app/core/` 配置、日志、加密、权限常量、OpenAPI 配置
  - `app/models/` SQLAlchemy 模型
  - `app/schemas/` Pydantic v2 契约
  - `app/crud/` 细粒度数据库访问
  - `app/services/runtime/` context builder、meta node、generator、scheduler、side effects
  - `app/services/jobs/` Redis chat dispatcher、Postgres durable job runner、重试与锁
  - `app/services/realtime/` WS 连接管理、Redis backplane 消费
  - `app/services/providers/` OpenAI-compatible chat/embedding 适配层
  - `app/services/prompts/` 模板加载、变量校验、渲染、快照
  - `app/services/memory/` pgvector 检索、摘要压缩、memory chunk 写入
  - `app/services/audit/` Run/Step/Artifact/Link
  - `app/services/storage/` artifact store 抽象，首版文件系统实现
  - `app/services/security/` RBAC、provider secret 加解密
  - `app/worker/` Worker 专属入口、容器与执行运行时
  - `app/main.py`
  - `tests/`
  - `alembic/`
  - `pyproject.toml`
- `frontend/`
  - React/Vite 应用
- `packages/ts-sdk/`
  - 由后端 OpenAPI 自动生成的 TS SDK
- `deploy/`
  - `docker-compose.yml`、Dockerfiles、env 模板、初始化脚本
- `docs/`
  - ADR、数据流、事件协议、Prompt 变量清单
- 根目录
  - `pnpm-workspace.yaml`
  - `Makefile`
  - `README.md`

### 2. 后端核心模块

领域实体按完整平台 v1 建模：

- 身份与权限：`users / roles / auth_sessions / invite_codes / invite_quota_grants / user_groups / user_group_members`
- 角色与模型：`characters / character_acl / model_providers / available_models / embedding_providers`
- 会话核心：`cocoons / session_states / messages / cocoon_tag_bindings / message_tags / memory_tags / tag_registry`
- 记忆与运行：`memory_chunks / failed_rounds`
- 任务与同步：`action_dispatches`、`durable_jobs`、`wakeup_tasks`、`cocoon_pull_jobs`、`cocoon_merge_jobs`、`checkpoints`
- 审计：`audit_runs / audit_steps / audit_artifacts / audit_links`
- Prompt：`prompt_templates / prompt_template_revisions / prompt_variables`
- Provider 密钥：`provider_credentials`，敏感字段加密存储

关键实现约束：

- `SessionState` 与 `Message` 强制拆表。
- ChatRuntime 作为唯一执行内核，所有事件统一映射为 `RuntimeEvent`。
- 短时聊天动作先写用户消息与 action ledger，再 enqueue Redis Stream。
- 耐久任务统一落 `durable_jobs`，通过 `FOR UPDATE SKIP LOCKED` claim。
- API 与 Worker 的 WS 回流通过 Redis Pub/Sub 或等价兼容层完成。
- Artifact store 采用兼容层抽象，首版实现为文件系统。
- 审计产物支持 TTL 与手动清理，不破坏审计索引。

### 3. Prompt 模板体系

Prompt 作为全局配置能力，不做角色级模板覆盖。角色只提供模板变量，例如：

- `character_settings`
- `session_state`
- `visible_messages`
- `memory_context`
- `runtime_event`
- `wakeup_context`
- `merge_context`
- `provider_capabilities`

实现方式：

- 模板语法使用“受限占位符”机制，不允许任意代码执行。
- `system/meta/generator/memory_summary/pull/merge/audit_summary` 都是可配置模板类型。
- 保存模板时校验必填变量、未知变量、模板类型兼容性。
- 配置保存后立即生效，但每次保存都生成不可变 revision，active revision 指针即时切换。
- 每次运行在 `AuditArtifact` 中保存：
  - 模板 ID
  - revision ID
  - 输入变量快照
  - 渲染后 Prompt 快照
- Provider secret、token 等敏感值不得进入模板变量或审计快照。

### 4. API、WS 与共享契约

后端对外分为以下接口族：

- `auth`
- `users / roles / invites / groups`
- `characters`
- `providers / embedding-providers`
- `tags`
- `prompt-templates`
- `cocoons`
- `messages / reply / user_message`
- `memory`
- `wakeup`
- `pulls / merges`
- `checkpoints / rollback`
- `audits / insights`
- `admin/artifacts`

必须稳定的公共契约：

- `POST /api/v1/cocoons/{id}/messages` 返回 `202 + action_id`
- `PATCH /api/v1/cocoons/{id}/user_message`
- `POST /api/v1/cocoons/{id}/reply/retry`
- `WS /api/v1/cocoons/{id}/ws`
- `POST /api/v1/prompt-templates/{template_type}`
- `PUT /api/v1/prompt-templates/{template_type}`
- `GET /api/v1/prompt-templates`
- `GET /api/v1/audits/{run_id}`

WS 事件统一定义：

- `dispatch_queued`
- `reply_started`
- `reply_chunk`
- `reply_done`
- `state_patch`
- `job_status`
- `error`

前端契约协作：

- 后端生成 OpenAPI schema。
- `packages/ts-sdk` 自动生成 TS client/types。
- frontend 仅消费 SDK，不手写请求类型。

### 5. 基础设施与运行链路

`deploy/docker-compose.yml` 默认启动：

- `api`
- `worker`
- `postgres`
- `redis`
- `minio` 保留 profile，暂不默认启用
- `frontend` 为可选开发 profile

默认工程选择：

- Python：`uv + ruff + pytest + mypy`
- ORM：`SQLAlchemy 2`
- 向量：`pgvector`
- 聊天 dispatch：`Redis Stream`
- WS backplane：`Redis Pub/Sub`
- 配置：`.env + pydantic-settings`
- 加密：应用级 master key 对 provider credentials 加密
- 观测：结构化日志 + metrics 预留

### 6. 语义记忆与向量测试约束

- `EmbeddingProvider` 支持多条配置记录，Web 端可同时展示和编辑 `local_cpu` 与 `openai_compatible` 配置。
- 运行时只允许 1 个启用中的 embedding provider。后端在 create/update 时以事务方式执行“启用当前项并停用其它项”的单活切换。
- 若没有启用中的 embedding provider，则聊天、审计、普通记忆写入继续工作，但向量检索路径直接跳过。
- 向量检索只在 Postgres 且 `vector` 扩展可用时启用；SQLite 不提供运行时向量检索回退。
- 新增 `memory_embeddings` 作为 `MemoryChunk` 的 embedding 持久层，写入顺序固定为 `MemoryChunk -> memory_embeddings -> embedding_ref`。
- 默认测试环境继续使用 SQLite；所有依赖向量检索的用例通过 `pgvector` 标记隔离，并在未配置 `COCOON_PGVECTOR_TEST_DATABASE_URL` 时自动跳过。

### 7. 运行时契约补充

- `AcceptedResponse` 现在包含 `debounce_until`，用于表达短窗防抖命中结果。
- 正常回复轮次的 WS 顺序固定为：
  1. `dispatch_queued`
  2. 初始 `state_patch`
  3. `reply_started`
  4. `reply_chunk*`
  5. `reply_done`
  6. 最终 `state_patch`
- 最终 `state_patch` 在 `scheduler_node` 和 `side_effects` 完成之后发送，并携带最新的 `current_wakeup_task_id`。
- 沉默轮次可以只发送单次 `state_patch` 并结束。

### 8. 对象级授权与后台任务约束

- 路由层保留全局 permission 检查，但 character、cocoon、message、memory、pull、merge、audit 的真实读写边界由对象级授权服务决定。
- Character 访问遵循“创建者、管理员、ACL user/role/group 可见”的规则。
- Cocoon 访问遵循“owner 始终可访问；其它用户必须同时满足全局 permission 与 character 可见性”的规则。
- isolated tag 规则落在数据层，不允许在消息窗口、memory 检索、pull 候选、merge 候选之间跨越不可见边界。
- `/admin/artifacts/cleanup` 与 `/admin/artifacts/cleanup/manual` 只负责入队 durable job，API 响应不再代表同步删除完成。

### 9. 审计与洞察补充

- `AuditStep` 统一收敛为 `context_builder`、`meta_node`、`generator_node`、`scheduler_node`、`side_effects` 五段。
- 新增 artifact kind：`memory_retrieval`、`provider_raw_output`、`side_effects_result`、`compaction_result`、`merge_conflict_report`、`workflow_summary`。
- `InsightsSummary` 在原有统计之外扩展 `model_usage`、`workflow_metrics`、`failed_rounds`、`relation_score_timeline` 四个 typed 区块。
- 失败轮次通过最小 `FailedRound` 记录补齐，仅用于统计与审计，不代表已实现完整恢复产品面。

## Test Plan

必须覆盖的测试与验收场景：

- 发送消息：用户消息入库、返回 `202`、Worker 处理、WS 正常收到 chunk 与 done。
- 幂等：同一 `client_request_id` 不重复写用户消息。
- 聊天动作丢失：Redis chat dispatch 未完成时，前端可通过 retry 安全恢复。
- Durable job：`merge/pull/rollback/wakeup` 在 Worker 重启后仍可继续 claim。
- RBAC：不同角色对 cocoon、character、providers、prompt templates 的权限生效。
- Prompt 模板：非法变量拒绝保存，合法更新后下一轮立即命中新 revision。
- Prompt 审计：运行记录能回看模板 revision、变量快照、渲染快照。
- Provider 管理：密钥加密存储，读取接口不回显原文。
- WS 跨进程：Worker 发布事件后，API 任意实例都能正确转发给连接用户。
- SessionState：`state_patch` 与消息存储顺序符合协议约束。
- Memory：标签过滤同时作用于消息与 memory 检索。
- pgvector：默认 SQLite 测试跳过向量用例，配置 `COCOON_PGVECTOR_TEST_DATABASE_URL` 后执行向量集成测试。
- Rollback：逻辑回退后有效视图正确，清理任务延迟执行。
- Artifact retention：TTL 清理与手动清理不破坏 audit 索引和回放摘要。
- OpenAPI SDK：后端接口变更后，TS SDK 能重新生成并通过 frontend 类型检查。

## Assumptions

- Prompt 模板全局唯一管理，不做角色覆盖；角色信息通过变量注入。
- “立即生效”表示保存即切 active revision，但保留 revision 历史供审计与回放。
- 聊天类 dispatch 可接受少量丢失，因此走 Redis；但所有 action 仍在数据库保留最小账本。
- Merge、Pull、Wakeup、Rollback、Compaction、Cleanup 都是耐久任务，必须持久化到 Postgres。
- 审计大对象首版存本地文件系统，通过兼容层封装，未来可切换到 MinIO/S3。
- 前端继续保留在同一仓库，但当前优先实现后端。
- `EmbeddingProvider` 的多配置单活规则由后端原子切换保证，不依赖前端先手动停用旧项。
