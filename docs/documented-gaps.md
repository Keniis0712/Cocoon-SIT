# 文档承诺与当前实现差异清单

更新时间：2026-04-18

## 范围

本清单对照以下文档与当前仓库实现：

- `README.md`
- `docs/backend-implementation-plan.md`
- `docs/data-flow.md`
- `docs/prompt-variables.md`
- `docs/ws-events.md`
- `current-architecture.md`
- `frontend-architecture.md`

这里只记录两类内容：

- 文档写了，但实现仍未完整落地
- 文档描述已经过期，需要按当前实现回写

## 一、仍需继续推进的后端项

| ID | 文档承诺 | 当前状态 | 结论 |
| --- | --- | --- | --- |
| B2 | `audit_summary` 应作为正式 prompt 变量进入统一渲染链路 | 目前仍主要以 artifact 形式落库，没有进入统一 prompt 变量主链路 | 缺失 |
| B3 | 保存 prompt 时应校验必填变量与模板兼容性 | 目前仍以未知变量校验为主，缺少必填变量缺失校验 | 半实现 |
| B6 | Pull / Merge 应完整覆盖增量锚点、冲突协调与状态融合 | 主链路已可用，但增量锚点与冲突协调仍偏轻量 | 半实现 |
| B7 | Rollback 应采用逻辑回退加延迟清理 | 目前仍以直接清理后续数据为主，没有完整“有效视图”层 | 半实现 |
| B8 | `FailedRound` 应承接失败轮次恢复与重试数据源 | 已补最小失败写入用于 insights，但恢复产品面仍未完整落地 | 半实现 |

## 二、F 系列前端/后台联动状态

### 已完成

| ID | 原问题 | 当前状态 | 结论 |
| --- | --- | --- | --- |
| F1 | WS 缺少断线重连、恢复补偿 | 已补 `useCocoonWs`，支持心跳、有限重连、REST 补偿 | 已完成 |
| F2 | 导航未按权限显示 | 侧边栏已改为基于真实 permission 过滤 | 已完成 |
| F3 | 缺少 `/cocoons`、`/audits`、`/insights`、`/merges` 页面 | 页面已存在，原 gap 属于文档过期 | 已完成 / 文档过期 |
| F4 | 缺少 `AuditsWorkbench`、`CocoonMemoryPage` | 页面已存在并接入路由 | 已完成 / 文档过期 |
| F5 | 审计与洞察页面缺少 richer UI | 当前已有图表、时序与详情页，原描述已过期 | 已完成 / 文档过期 |
| F6 | Workspace 看不到当前 wakeup | 已补 `current_wakeup_task_id` 展示与恢复逻辑 | 已完成 |
| F7 | `Chat Groups` 暴露了未实现能力 | 入口已收口，页面明确标注为未开放能力 | 已完成 |
| F8 | `Settings` 依赖前端假数据和假动作 | 已收口为真实后端支持的设置/维护能力 | 已完成 |
| F9 | Provider 页面同步/测试/删除是假动作 | 已补真实后端接口，前端恢复为可用动作 | 已完成 |
| F10 | Character 页面删除角色、删除 ACL 只是前端承诺 | 已补后端删除角色与删除单条 ACL，前端恢复对应入口 | 已完成 |
| F11 | Groups 页面编辑、删组、移除成员未落地 | 已补后端接口并恢复前端入口 | 已完成 |
| F12 | Invites 页面撤销邀请码、额度下发、摘要/记录是假动作 | 已补后端 revoke / grant / summary API，并恢复前端真实交互 | 已完成 |
| F13 | Cocoon/Memory/Tag 的删除或解绑入口是旧假动作 | 已补删除 cocoon、删除 memory、解绑 tag 后端接口，并恢复前端 | 已完成 |
| F14 | Tag UI 暗示支持解绑但后端不支持 | 已补 tag 解绑 API，工作台恢复真实移除交互 | 已完成 |
| F15 | 用户/邀请码页展示伪造额度摘要 | 邀请页摘要与 grant 列表已切到真实后端数据 | 已完成 |

## 三、文档明显过期的部分

| ID | 文档说法 | 实际状态 | 结论 |
| --- | --- | --- | --- |
| D1 | `frontend-architecture.md` 仍把旧页面结构写成当前实现 | 当前前端目录、路由与组件职责已明显调整 | 文档过期 |
| D2 | 若干架构文档仍以旧 runtime / audit / memory 模块命名为准 | 代码已收敛到新 runtime / audit / memory 路径 | 文档过期 |
| D3 | 若干文档仍默认前端暴露更多旧版运维动作 | 前端现已收口到真实后端能力 | 文档过期 |

## 四、建议的后续顺序

1. 继续补齐剩余后端主链路：`B2`、`B3`、`B6`、`B7`、`B8`
2. 统一回写架构文档，删掉已经过期的旧命名与旧页面说明
3. 对本轮新增的 invite / quota / revoke / summary 行为补更细的开发者文档与验收说明
