# 文档承诺与当前实现差异清单

更新时间：2026-04-18

## 范围

本清单对照以下文档与当前代码实现：

- `README.md`
- `docs/backend-implementation-plan.md`
- `docs/data-flow.md`
- `docs/prompt-variables.md`
- `docs/ws-events.md`
- `current-architecture.md`
- `frontend-architecture.md`

说明：

- 这里只记录“文档里明确写了，但代码未实现、只建模未接线、或实现明显不完整”的内容。
- 已经补上的内容不再重复列出，例如：WS 鉴权、`meta/system/memory_summary` 模板接线、基础 wakeup 调度。
- 有些差异属于“文档过期”，不是单纯代码缺功能；这类会单独归档。

## 一、确认存在的后端能力缺口

| ID | 文档承诺 | 当前代码现状 | 判断 |
| --- | --- | --- | --- |
| B1 | 文档多处把“长期记忆与语义检索 / pgvector / embedding provider”写成当前平台能力，例如 `docs/backend-implementation-plan.md`、`current-architecture.md` 4.6、10.2、10.4。 | `backend/app/services/memory/service.py` 只有“按时间倒序 + tag 过滤”的普通 SQL 读取；`EmbeddingProvider` 只在 `backend/app/api/routes/providers.py` 里做 CRUD；运行时、记忆检索、压缩链路里都没有 embedding 生成或向量检索。 | 缺失 |
| B2 | `audit_summary` 被文档定义为正式 Prompt 模板类型，且应参与运行链路，见 `docs/backend-implementation-plan.md` 3。 | `backend/app/services/prompts/registry.py` 注册了 `audit_summary`，但代码里没有任何 `prompt_service.render(..., template_type=\"audit_summary\")`；当前只有 `backend/app/worker/durable_executor.py` 直接写 `audit_summary` 类型 artifact。 | 缺失 |
| B3 | 保存 Prompt 时要校验“必填变量、未知变量、模板类型兼容性”，见 `docs/backend-implementation-plan.md` 3。 | `backend/app/services/prompts/service.py` 目前只校验“未知变量”；没有校验“该模板是否包含必须变量”，也没有更严格的类型兼容检查。 | 半实现 |
| B4 | `audit cleanup` 被文档列为 durable job 类别，任务真相源应落 Postgres，见 `docs/backend-implementation-plan.md` Summary。 | `backend/app/api/routes/admin_artifacts.py` 的 `/cleanup` 和 `/cleanup/manual` 直接在 API 进程里执行删除；虽然模型里有 `DurableJobType.artifact_cleanup`，但 API 没有走 durable queue。 | 半实现 |
| B5 | `SchedulerNode` 除唤醒外，还应处理“后置压缩”“Pull/Merge 后追加任务”，见 `current-architecture.md` 7.6。 | `backend/app/services/runtime/scheduler_node.py` 现在只消费 `next_wakeup_hint` 并安排 wakeup；`auto_compaction_enabled` 仅建模于 `backend/app/models/entities.py`，运行时从未使用。 | 半实现 |
| B6 | Pull 应按“上次同步锚点后的新增内容”构造候选集，Merge 应做冲突调和与状态融合，见 `current-architecture.md` 12。 | `backend/app/api/routes/pulls.py`、`merges.py` 只是入队；`backend/app/services/runtime/context_builder.py` 直接读源 cocoon 当前可见消息/记忆；没有同步水位、没有增量 anchor、没有 merge conflict report。 | 半实现 |
| B7 | Rollback 应采用“逻辑回退 + 延迟清理”，保证恢复性和审计可追溯，见 `current-architecture.md` 3.6、13.2、13.3。 | `backend/app/worker/durable_executor.py::_rollback` 调 `RoundCleanupService._delete_message_related_rows()` 立即删除后续消息、记忆和审计；不存在“当前有效视图”层，也没有单独延迟清理任务。 | 半实现 |
| B8 | `FailedRound` 应用于失败轮次记录、前端重试与恢复，见 `current-architecture.md` 4.7、16.2。 | `backend/app/models/entities.py` 定义了 `FailedRound`，但全仓库没有任何创建记录的代码；`backend/app/services/runtime/round_cleanup.py` 只会删除它。 | 缺失 |
| B9 | 审计链应覆盖 `context_builder -> meta_node -> generator_node -> scheduler_node -> side_effects`，并保存检索结果、模型原始返回、压缩结果、Merge 冲突报告等，见 `current-architecture.md` 14。 | `backend/app/services/runtime/chat_runtime.py` 没有单独的 `side_effects` step；当前 artifact 主要是 prompt snapshot、prompt variables、meta output、generator output 和少量 summary，没有“检索结果 artifact”“模型原始返回 artifact”“merge conflict report”。 | 半实现 |
| B10 | 正常对话的 WS 顺序建议是 `dispatch_queued -> state_patch/reply_started -> reply_chunk* -> reply_done -> 最终 state_patch`，见 `current-architecture.md` 6.3。 | `backend/app/services/runtime/chat_runtime.py` 只在生成前发一次 `state_patch`，`reply_done` 后没有最终状态补丁。 | 半实现 |
| B11 | `SessionState` 的核心字段应包括 `current_wakeup_task_id`，见 `current-architecture.md` 4.4。 | 模型里有该字段：`backend/app/models/entities.py`；但 API 输出 `backend/app/schemas/cocoon.py::SessionStateOut` 没有它，前端也无法直接看到“当前计划中的下一次 wakeup”。 | 半实现 |
| B12 | 文档里的 `DispatchJob`/`202 Accepted` 语义包含 `debounce_until`，用于极短时间内的重复提交控制，见 `current-architecture.md` 6.1、8.3。 | `backend/app/schemas/common.py::AcceptedResponse` 只有 `accepted/action_id/status`；`ActionDispatch` 模型里也没有 `debounce_until`，当前只有 `client_request_id` 幂等，没有短窗口防抖。 | 缺失 |
| B13 | 文档强调标签、角色 ACL、群组、owner 等都应参与访问边界，见 `current-architecture.md` 3.4、4.1、4.2、15。 | `backend/app/services/security/rbac.py` 只做“全局 permission 名称是否存在”；`CharacterAcl`、`owner_user_id`、`UserGroupMember` 目前没有进入任何对象级访问判断。 | 半实现 |
| B14 | 文档把 `MemoryChunk` 描述为“向量化长期记忆切片”，并期望检索结果可进入审计链，见 `current-architecture.md` 4.6、14.3。 | 当前 `MemoryChunk` 只有普通文本和 `embedding_ref` 字段；没有向量写入逻辑，也没有把“本轮实际取回了哪些 memory”记录成 artifact。 | 半实现 |
| B15 | 文档强调 Insights 能派生 token 消耗、模型调用次数、唤醒次数、Pull/Merge 成功率、失败轮次分布、关系分变化轨迹，见 `current-architecture.md` 14.5。 | `backend/app/api/routes/insights.py` 目前只返回用户数、消息数、memory 数、audit 数，以及 action/job 状态计数；没有 token、模型、关系轨迹等指标。 | 半实现 |

## 二、确认存在的前端与契约缺口

| ID | 文档承诺 | 当前代码现状 | 判断 |
| --- | --- | --- | --- |
| F1 | `useCocoonWS` 应补上心跳、有限重连、连接恢复后的 REST 补偿拉取，见 `frontend-architecture.md` 6。 | `frontend/src/hooks/useWorkspaceWs.ts` 只有 `ping` 心跳和关闭清理；没有断线重连逻辑，也没有 hook 内部的恢复补偿。 | 半实现 |
| F2 | 导航项可见性应由用户权限决定，见 `frontend-architecture.md` 8.2。 | `frontend/src/components/AppShell.tsx` 的 `navItems` 是硬编码常量，没有按 permission 过滤。 | 缺失 |
| F3 | 前端页面族应包含 `/cocoons`、`/cocoons/:id`、`/cocoons/:id/memory`、`/audits`、`/insights`、`/merges` 等更细分页面，见 `frontend-architecture.md` 3.2。 | 当前 `frontend/src/App.tsx` 只有 `/`、`/workspace`、`/access`、`/catalog`、`/operations`、`/login`；不少文档中的独立页面并不存在。 | 半实现 |
| F4 | 文档中的 `AuditsWorkbench`、`CocoonMemoryPage` 等工作台/审计页应独立存在，见 `frontend-architecture.md` 3.3、10。 | 当前没有这些页面组件；审计详情主要在 `frontend/src/pages/OperationsPage.tsx` 里以 JSON dump 方式查看。 | 缺失 |
| F5 | 审计与洞察页应有图表、时间轴、树状节点等 richer UI，见 `frontend-architecture.md` 10.3。 | `frontend/src/pages/DashboardPage.tsx` 和 `OperationsPage.tsx` 目前是基础卡片、列表和原始 JSON，没有图表、时间轴、树状审计工作台。 | 半实现 |
| F6 | 文档把当前计划中的 wakeup 视为核心状态之一。 | 前端只能在 `OperationsPage` 看全部 wakeup 列表，`WorkspacePage` 无法直接显示“当前 cocoon 已计划的下一次 wakeup”；根因也包括 `SessionStateOut` 未暴露 `current_wakeup_task_id`。 | 半实现 |
| F7 | 旧版前端保留了 `Chat Groups` 页面与管理入口，文档也把群聊/群组协作当成工作台能力的一部分，见 `frontend-architecture.md` 3.2、8。 | `frontend/src/api/chatGroups.ts` 目前直接返回空列表；创建、编辑、删除全部走 `unsupportedFeature(...)`，说明前端入口还在，但后端没有对应能力。 | 缺失 |
| F8 | `Settings` 页面默认承载系统设置查看、修改与清理动作，见 `frontend-architecture.md` 8.5。 | `frontend/src/api/settings.ts` 读取的是前端硬编码 `DEFAULT_SETTINGS`；`updateSystemSettings()` 和 `triggerRollbackCleanup()` 都直接报“不支持”。页面存在，但并未接到真实后端配置。 | 缺失 |
| F9 | Provider 管理页默认包含“手动同步模型 / 连通性测试 / 删除 provider”等运维动作，见 `frontend-architecture.md` 8.4。 | `frontend/src/api/providers.ts` 中这三类动作都直接走 `unsupportedFeature(...)`；当前后端只支持基础 CRUD，不支持旧版前端保留的更完整运维能力。 | 半实现 |
| F10 | 角色卡管理不只要支持创建/编辑，还应支持精细 ACL 管理与资源清理，见 `frontend-architecture.md` 8.3。 | `frontend/src/api/characters.ts` 里删除角色卡、删除单条 ACL 都是 `unsupportedFeature(...)`；当前只能新增或整体覆盖 ACL，无法完成旧版页面提供的精细管理动作。 | 半实现 |
| F11 | 群组页保留了“编辑群组 / 删除群组 / 移除成员”的完整管理交互。 | `frontend/src/api/groups.ts` 里这三类动作都未接后端；当前只支持列表、创建和新增成员，页面能力明显超出后端实际能力。 | 半实现 |
| F12 | 邀请码与额度管理页保留了“撤销邀请码 / 发放邀请码额度 / 查看额度记录”的入口。 | `frontend/src/api/invites.ts` 中撤销邀请码与直接发放额度都未实现；`listInviteGrants()` 目前固定返回空页，说明页面入口还在，但后端并没有配套能力。 | 缺失 |
| F13 | Cocoon 工作台保留了“删除 cocoon / 删除 memory / 删除 reply / 编辑用户消息并重跑”等旧版高级动作。 | `frontend/src/api/cocoons.ts` 里这些动作全部是 `unsupportedFeature(...)`；当前后端只覆盖基础聊天、memory compaction、retry 等主链路，没有把这些高级编辑/清理动作开放出来。 | 半实现 |
| F14 | 标签系统按旧版页面语义应支持“增删绑定”，用于快速切换 cocoon 的可见上下文。 | `frontend/src/api/tags.ts` 只能补增缺失 tag；如果目标集合比现有集合更少，会直接报“不支持移除 tags”。这意味着旧 UI 中“解除绑定”操作没有真实后端能力。 | 半实现 |
| F15 | 前端的用户/邀请码管理还保留了“额度摘要”这类信息展示，按文档应来自真实后端配额系统。 | `frontend/src/api/admin-users.ts::getUserInviteSummary()` 目前直接返回固定值，不读取任何后端数据；说明旧页面中的该信息仍是占位实现。 | 半实现 |

## 三、文档已明显过期或与现状不一致的部分

这些项不一定意味着“产品功能缺失”，但它们已经不能准确描述当前代码。

| ID | 文档说法 | 代码现状 | 判断 |
| --- | --- | --- | --- |
| D1 | `frontend-architecture.md` 声称当前前端技术栈是 `Tailwind CSS 4 + shadcn/ui + Radix UI + Lucide + Axios + i18next + sonner + ECharts`。 | `frontend/package.json` 实际只有 `react`、`react-router-dom`、`zustand` 和 Vite/TS 基础依赖；样式来自 `frontend/src/index.css`，网络层走 `packages/ts-sdk/src/client.ts` 的 `fetch` 封装。 | 文档过期 |
| D2 | `frontend-architecture.md` 里把当前目录结构写成包含 `frontend/src/router.tsx`、`frontend/src/locales/` 等。 | 当前路由写在 `frontend/src/App.tsx`；`locales/` 不存在。 | 文档过期 |
| D3 | `current-architecture.md` 用 `DispatchJob`、`vector_memory.py`、`chat_runtime_v2.py`、`cocoon_merge_v2.py`、`rollback_cleanup.py`、`ai_audit.py` 等模块名描述“当前实现”。 | 实际代码已经收敛到 `ActionDispatch`、`DurableJob`、`app/services/runtime/*`、`app/services/audit/service.py`、`app/services/memory/service.py` 等路径。 | 文档过期 |
| D4 | `docs/backend-implementation-plan.md` 与 `current-architecture.md` 都把 `packages/ts-sdk` 描述为“自动生成的 TS client/types”。 | `packages/ts-sdk/package.json` 的 `generate` 只生成 `src/generated.ts` 类型；`src/client.ts` 是手写请求客户端，不是生成物。 | 半实现 / 文档过期 |
| D5 | `frontend-architecture.md` 默认前端使用 `Axios` 拦截器与 `useUserStore`/`useChatSessionStore` 命名。 | 当前实现是 `useAuthStore`、`useWorkspaceStore`，并通过 `frontend/src/api/client.ts` 包装共享 SDK 做 token refresh。 | 文档过期 |

## 四、文档中写了但测试计划仍未真正覆盖的项

这一部分不是功能缺失，而是“文档里把它当成验收项，但当前测试并未系统证明”。

| ID | 文档验收项 | 当前测试情况 | 判断 |
| --- | --- | --- | --- |
| T1 | Redis chat dispatch 丢失后，前端可通过 retry 安全恢复，见 `docs/backend-implementation-plan.md` Test Plan。 | 现有测试覆盖了 `retry` 接口基础链路，但没有模拟“dispatch 丢失/未完成”后的恢复场景。 | 未覆盖 |
| T2 | WS 跨进程转发正确，见 `docs/backend-implementation-plan.md` Test Plan。 | 现有测试只覆盖单进程/in-memory TestClient，没有多 API 实例 + Redis backplane 的回流验证。 | 未覆盖 |
| T3 | Prompt 保存时“必填变量”校验，见 `docs/backend-implementation-plan.md` 3。 | 测试只覆盖“未知变量拒绝保存”和 revision 立即生效，没有“必填变量缺失被拒绝”的断言。 | 未覆盖 |
| T4 | Artifact retention 不破坏 audit 索引和回放摘要，见 `docs/backend-implementation-plan.md` Test Plan。 | 现有测试只验证 artifact 可以被清理，没有验证清理后 audit 回放/摘要仍然成立。 | 未覆盖 |
| T5 | OpenAPI 变更后 SDK 可重新生成并通过前端类型检查，见 `docs/backend-implementation-plan.md` Test Plan。 | 当前有 `sdk:generate` 脚本，但测试/CI 面没有自动执行“dump OpenAPI -> regenerate SDK -> frontend typecheck”的链路。 | 未覆盖 |

## 五、建议的使用方式

如果后续要继续补功能，建议按下面顺序处理：

1. 先补运行时核心缺口：`B1`、`B6`、`B7`、`B9`、`B13`。
2. 再补契约与运维缺口：`B4`、`B10`、`B11`、`B12`。
3. 然后处理前端缺口：`F1`、`F2`、`F4`、`F6`。
4. 最后统一清理文档过期项：`D1` 到 `D5`。

## 六、暂不列入本清单的已完成项

以下内容已在当前代码中落地，因此不再视为缺口：

- WebSocket 鉴权
- `system` / `meta` / `generator` / `memory_summary` Prompt 接线
- Prompt 渲染进入审计链
- 基础 wakeup 调度与 future `run_at` 生效
- `wakeup_context` / `merge_context` / `provider_capabilities` 模板变量可用
