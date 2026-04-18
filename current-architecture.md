# Cocoon-SIT 后端设计与实现说明（统一协议版）

## 0. 文档说明

本文档描述的是 Cocoon-SIT 在“统一通信协议”之后的后端设计与实现标准。目标不是做概览，而是把系统拆到足够细，使读者可以据此直接重建当前完整功能。

本文档采用以下约定：

- 所有客户端触发的对话行为，统一采用 `HTTP 202 Accepted` 入队。
- 所有实时生成与状态回流，统一通过 `WebSocket` 事件流下发。
- `ChatRuntime` 是唯一的会话执行内核。普通对话、编辑、重试、唤醒、Pull、Merge 都只是不同的 `event_type`。
- `SessionState` 与 `Message` 强制拆表。静态对话和动态心智不能混存。
- 标签系统不是装饰字段，而是上下文过滤、权限边界、分支隔离和记忆检索的核心机制。
- 审计链不是附加日志，而是产品能力的一部分，用于 Insights、回放、溯源与调试。
- 默认开发和测试仍以 SQLite 为主，但语义向量检索只在 Postgres + `vector` 扩展环境下启用。

历史上仓库里可能存在迁移期的兼容写法，但若要复刻系统，应以本文档为准，而不是以旧链路为准。

---

## 1. 项目定位与核心概念

### 1.1 项目定位

Cocoon-SIT 是一个围绕 `Cocoon` 概念构建的 AI 角色扮演与记忆工作台。它不是一个简单聊天应用，而是一个把以下能力统一建模的“会话操作系统”：

- 角色与人格设定
- 分支会话与父子继承
- 长期记忆与语义检索
- 动态心智状态
- 主动唤醒
- Pull / Merge 同步
- Checkpoint / Rollback
- 全链路审计

### 1.2 Cocoon 的含义

一个 `Cocoon` 可以理解为“一个独立角色宇宙的运行容器”。它至少包含以下内容：

- 一个角色设定 `Character`
- 一个模型选择 `selected_model_id`
- 一组可见历史消息
- 一份独立的 `SessionState`
- 一组已绑定或已激活的标签
- 一个父子分支位置
- 一组检查点、同步任务、唤醒任务和审计记录

### 1.3 关键术语

- `Root Cocoon`：没有父节点的主宇宙。
- `Child Cocoon`：从父 Cocoon 分叉出来的子宇宙。
- `SessionState`：当前会话的动态心智，包含好感度、人格偏移、活跃标签、当前唤醒任务等。
- `Message`：对话表层记录，承载用户消息、助手消息和内部系统消息。
- `Tag`：对话与记忆的可见性滤镜，也是检索和隔离的核心边界。
- `MemoryChunk`：向量化的长期记忆切片。
- `DispatchJob`：异步执行单元，负责把 HTTP 请求转交给后台执行器。
- `WakeupTask`：定时触发的主动唤醒任务。
- `Pull`：后代 Cocoon 向祖先吸收新知识。
- `Merge`：子分支把自己的心智增量回流到主线。
- `Checkpoint`：某个安全回退锚点。
- `AuditRun`：一次 AI 运行的完整审计主记录。

---

## 2. 仓库结构与职责分层

### 2.1 顶层分层

后端按职责切分为五层：

- `app/models/`：ORM 模型，定义持久化结构。
- `app/schemas/`：Pydantic 契约，定义输入输出和内部结构化载荷。
- `app/crud/`：细粒度数据库读写，不承载跨实体业务编排。
- `app/services/`：业务层、运行时引擎、记忆、同步、回滚、审计、调度。
- `app/api/routes/`：HTTP / WebSocket 路由层，只做鉴权、校验、入队和连接管理。

### 2.2 关键模块职责

实现时建议保持以下模块边界：

- `app/main.py`：应用组装、路由注册、生命周期启动。
- `app/api/routes/cocoons.py`：Cocoon 相关 HTTP 与 WS 接口。
- `app/services/chat_runtime_v2.py`：统一运行时图结构。
- `app/services/batch_dispatch.py`：异步入队后的后台扫描与执行入口。
- `app/services/cocoon_realtime.py`：WebSocket 连接管理与广播。
- `app/services/vector_memory.py`：向量记忆读写与检索。
- `app/services/memory_service.py`：兼容或迁移期的记忆整理逻辑。
- `app/services/wakeup_tasks.py`：主动唤醒调度。
- `app/services/cocoon_sync_jobs.py`：Pull / Merge 后台任务。
- `app/services/cocoon_merge_v2.py`：Merge 的人格融合与冲突调和。
- `app/services/cocoon_vcs.py`：Checkpoint / Rollback 的时序与指针管理。
- `app/services/rollback_cleanup.py`：回滚后的延迟清理。
- `app/services/ai_audit.py`：运行审计与洞察面板数据源。
- `app/services/runtime_side_effects.py`：消息、状态、记忆、审计的统一副作用落库。

### 2.3 分层原则

- 路由层不能直接阻塞等待模型输出。
- 运行时层不感知 HTTP，只处理结构化 `RuntimeEvent`。
- WebSocket 层不做业务判断，只负责事件广播。
- CRUD 层不做跨流程编排。
- 任何需要追溯的动作，都必须映射到 `AuditRun -> AuditStep -> AuditArtifact`。

---

## 3. 核心设计原则

### 3.1 单向异步

客户端发起动作后只得到“已接收”的结果，不等待模型完成。真正的执行在后台完成，前端只通过 WS 观察状态推进。

### 3.2 统一运行时

普通对话、修改消息、重试生成、唤醒、Pull、Merge 统一归一为 `ChatRuntime(event_type, payload)`。避免一类能力一套流水线。

### 3.3 静态对话与动态心智分离

`Message` 记录“说过什么”，`SessionState` 记录“现在怎么想”。这两者具有完全不同的更新节奏、回滚语义和检索方式，不能混在同一张表或同一份 JSON 里。

### 3.4 标签即路由

标签系统同时承担四个角色：

- 决定消息的可见性边界
- 决定长期记忆的检索范围
- 决定群聊或分支中的隐私隔离
- 决定 Pull / Merge 时哪些内容可被吸收

### 3.5 状态先于文本

模型生成并不只产生回复文本，还会先产生状态判断：

- 要不要说话
- 好感度怎么变
- 人格补丁怎么改
- 是否新增/移除标签
- 是否安排下一次唤醒

因此必须先有 `Meta Node`，再有 `Generator Node`。

### 3.6 回滚采用逻辑回退

回滚不是立刻物理删除后续内容，而是先把当前宇宙的有效视图指针拨回锚点，再由后台清理器延迟清除冗余数据，保障可恢复性和审计可追溯性。

### 3.7 审计是产品功能

审计数据不是开发期日志，而是正式产品能力。Insights、成本看板、问题复盘和运行回放都依赖审计链完整性。

---

## 4. 核心领域模型

### 4.1 身份与权限

系统需要完整的身份层：

- `User`：基础用户实体。
- `Role`：角色定义，挂载 `permissions_json`。
- `AuthSession`：Refresh Token 会话与全局失效控制。
- `InviteCode`：邀请体系入口。
- `InviteQuotaGrant`：邀请额度发放记录。
- `UserGroup` / `UserGroupMember`：群组与成员归属。

### 4.2 角色与模型

- `Character`：系统角色或用户自定义角色，包含 Prompt、背景设定、默认风格。
- `CharacterAcl`：角色的可见性与使用权限。
- `ModelProvider` / `AvailableModel`：兼容 OpenAI 协议的模型提供方与模型清单。
- `EmbeddingProvider`：Embedding 的本地/远程来源。允许多配置共存，但任一时刻只能有一个启用项；启用某项时其余项必须自动失活。

### 4.3 Cocoon 主体

`Cocoon` 本体负责保存“宇宙壳层”信息，而不是心智细节：

- `id`
- `parent_id`
- `name`
- `owner_uid`
- `character_id`
- `selected_model_id`
- `created_at`

根据产品复杂度，也可以补充：

- `summary_model_id`
- `default_temperature`
- `max_context_messages`
- `auto_compaction_enabled`
- `rollback_anchor_msg_id`

### 4.4 SessionState

`SessionState` 必须一对一绑定 Cocoon，用于表达“此刻这个角色正处于什么心理状态”：

- `cocoon_id`
- `relation_score`
- `persona_json`
- `active_tags_json`
- `current_wakeup_task_id`
- `updated_at`

这张表是整个系统最关键的动态状态表。

### 4.5 Message 与标签体系

`Message` 是所有对话历史的载体。核心字段：

- `id`
- `cocoon_id`
- `client_request_id`
- `role`
- `content`
- `is_thought`
- `tags_json`
- `created_at`

标签体系至少包含：

- `TagRegistry`：标签定义与语义说明。
- `CocoonTagBinding`：Cocoon 绑定过哪些标签。
- `MessageTag`：消息级标签映射。
- `MemoryTag`：记忆级标签映射。

### 4.6 MemoryChunk

长期记忆建议使用关系库存元数据、向量库存 embedding：

- `id`
- `cocoon_id`
- `source_message_id`
- `content`
- `summary`
- `tags_json`
- `scope`
- `embedding_ref`
- `created_at`

其中 `scope` 至少区分：

- `dialogue`
- `summary`
- `pull`
- `merge`
- `system`

另外应补充独立的 `MemoryEmbedding` 持久层，用于记录：

- `memory_chunk_id`
- `embedding_provider_id`
- `model_name`
- `dimensions`
- `embedding`
- `created_at`

`MemoryChunk.embedding_ref` 只负责指向对应的 embedding 记录。

### 4.7 异步执行与系统事件

后台执行层至少需要三类实体：

- `DispatchJob`：客户端动作入队后的执行单元。
- `InternalEvent`：系统内部触发的事件，例如唤醒、同步、回滚清理。
- `FailedRound`：失败轮次记录，用于前端重试、审计和恢复。

### 4.8 同步、回滚与审计

高级能力依赖以下实体：

- `Checkpoint`：时光倒流的锚点。
- `CocoonPullJob`：Pull 任务。
- `CocoonMergeJob`：Merge 任务。
- `AuditRun`：一次运行的总记录。
- `AuditStep`：运行中的阶段节点。
- `AuditArtifact`：Prompt、检索结果、结构化输出、模型返回等产物。
- `AuditLink`：多个 Artifact 或 Step 的引用关系。

---

## 5. 数据库基建（Persistence Layer）

### 5.1 最低可行主表

以下四张表体现系统最核心的拆分方式：`Cocoon`、`SessionState`、`Message`、`TagRegistry`。

```sql
CREATE TABLE cocoons (
    id VARCHAR(64) PRIMARY KEY,
    parent_id VARCHAR(64) NULL,
    name VARCHAR(128) NOT NULL,
    character_id VARCHAR(64) NOT NULL,
    owner_uid VARCHAR(64) NOT NULL,
    selected_model_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE session_states (
    cocoon_id VARCHAR(64) PRIMARY KEY REFERENCES cocoons(id),
    relation_score INTEGER DEFAULT 0,
    persona_json JSONB DEFAULT '{}',
    active_tags_json JSONB DEFAULT '[]',
    current_wakeup_task_id VARCHAR(64) NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    cocoon_id VARCHAR(64) REFERENCES cocoons(id),
    client_request_id VARCHAR(128) UNIQUE,
    role VARCHAR(20) CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    is_thought BOOLEAN DEFAULT FALSE,
    tags_json JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tag_registry (
    tag_id VARCHAR(64) PRIMARY KEY,
    brief TEXT NOT NULL,
    is_isolated BOOLEAN DEFAULT FALSE
);
```

### 5.2 建议补充表

若要复刻完整功能，还必须补足以下表族：

```sql
CREATE TABLE memory_chunks (
    id BIGSERIAL PRIMARY KEY,
    cocoon_id VARCHAR(64) NOT NULL REFERENCES cocoons(id),
    source_message_id BIGINT NULL REFERENCES messages(id),
    scope VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    summary TEXT NULL,
    tags_json JSONB DEFAULT '[]',
    meta_json JSONB DEFAULT '{}',
    embedding_ref VARCHAR(128) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dispatch_jobs (
    id VARCHAR(64) PRIMARY KEY,
    cocoon_id VARCHAR(64) NOT NULL REFERENCES cocoons(id),
    event_type VARCHAR(32) NOT NULL,
    status VARCHAR(20) NOT NULL,
    lock_key VARCHAR(128) NOT NULL,
    debounce_until TIMESTAMP NULL,
    payload_json JSONB DEFAULT '{}',
    error_text TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE wakeup_tasks (
    id VARCHAR(64) PRIMARY KEY,
    cocoon_id VARCHAR(64) NOT NULL REFERENCES cocoons(id),
    run_at TIMESTAMP NOT NULL,
    reason TEXT NULL,
    payload_json JSONB DEFAULT '{}',
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE checkpoints (
    id VARCHAR(64) PRIMARY KEY,
    cocoon_id VARCHAR(64) NOT NULL REFERENCES cocoons(id),
    anchor_msg_id BIGINT NOT NULL REFERENCES messages(id),
    label VARCHAR(128) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_runs (
    id VARCHAR(64) PRIMARY KEY,
    cocoon_id VARCHAR(64) NOT NULL REFERENCES cocoons(id),
    action_id VARCHAR(64) NULL,
    operation_type VARCHAR(32) NOT NULL,
    status VARCHAR(20) NOT NULL,
    trigger_event_uid VARCHAR(128) NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP NULL
);
```

### 5.3 为什么必须拆出 SessionState

如果把好感度、当前人格、活跃标签直接塞回 `cocoons.meta_json`，会立刻遇到三个问题：

- 回滚无法表达“消息回退了，但心智也要一起回退到哪个时刻”。
- Pull / Merge 无法局部合并心智增量。
- 状态变化的审计粒度过粗，Insights 无法统计人格变化和关系波动。

因此 `SessionState` 必须是一等实体。

---

## 6. 统一通信契约（The Protocol）

### 6.1 触发端：REST 202

所有会触发模型执行的客户端行为都遵循相同模式：

- `POST /api/v1/cocoons/{id}/messages`
- `PATCH /api/v1/cocoons/{id}/user_message`
- `POST /api/v1/cocoons/{id}/reply/retry`

这三个接口都只做三件事：

- 校验权限与参数
- 必要时写入或清理数据库
- 创建 `DispatchJob` 并立即返回 `202 Accepted`

请求示例：

```json
{
  "content": "刚才的测试跑通了，累死了。",
  "client_request_id": "uuid-v4-abc",
  "timezone": "Asia/Tokyo"
}
```

响应示例：

```json
{
  "accepted": true,
  "action_id": "job-12345",
  "debounce_until": 1712345678
}
```

其中：

- `accepted` 表示服务端已接收并入队。
- `action_id` 是本次运行的主相关键，可用于日志、审计和前端状态关联。
- `debounce_until` 用于控制极短时间内的重复提交。

### 6.2 接收端：WebSocket 统一事件流

前端进入工作台后保持单一连接：

- `WS /api/v1/cocoons/{id}/ws`

所有运行时事件都从该连接下发，不再区分“新消息走 WS、编辑重试走 SSE”。

建议的事件联合类型如下：

```ts
type WsEvent =
  | { type: "dispatch_queued"; queue_length: number }
  | { type: "reply_started"; action_id: string }
  | { type: "reply_chunk"; text: string }
  | { type: "reply_done"; final_message_id: string }
  | {
      type: "state_patch";
      relation_score: number;
      active_tags: string[];
      current_wakeup_task_id?: string | null;
    }
  | { type: "error"; reason: string };
```

### 6.3 事件顺序约束

一次正常对话建议遵循如下顺序：

1. `dispatch_queued`
2. 初始 `state_patch`
3. `reply_started`
4. `reply_chunk` 若干次
5. `reply_done`
6. 最终 `state_patch`

如果 `Meta Node` 判断本轮应沉默，则允许出现：

1. `dispatch_queued`
2. `state_patch`
3. 结束，无 `reply_started`

### 6.4 幂等、重连与容错

实现时必须保留以下语义：

- `client_request_id` 用于幂等，避免重复落用户消息。
- `action_id` 用于把 HTTP 入队与 WS 回流关联起来。
- WS 重连后，前端应从 REST 拉取最新消息与 `SessionState` 进行补偿。
- WS 不是唯一真相源，数据库才是最终真相源。

---

## 7. 后端 V2 运行时引擎（ChatRuntime）

### 7.1 运行时输入

后台执行器从 `DispatchJob` 读取一个统一事件：

```python
RuntimeEvent(
    event_type="chat" | "edit" | "retry" | "wakeup" | "pull" | "merge",
    cocoon_id="...",
    action_id="...",
    payload={...}
)
```

### 7.2 运行时节点

统一运行时建议拆为以下节点：

- `context_builder`
- `meta_node`
- `generator_node`
- `scheduler_node`
- `side_effects`

### 7.3 Context Builder

输入是 `RuntimeEvent`，输出是结构化上下文包。它必须负责：

- 加载 `Cocoon`
- 加载 `SessionState`
- 加载最近消息
- 根据活跃标签过滤消息与记忆
- 检查当前是否存在回滚锚点或待清理区间
- 查询长期记忆
- 生成最终 Prompt 所需的上下文对象

最关键的规则是：消息和记忆都必须按标签过滤，不能只过滤消息。检索命中的 message/memory 结果还应作为 `memory_retrieval` 审计产物保存，供回放和洞察复用。

### 7.4 Meta Node

Meta Node 先于文本生成。其任务不是写回复，而是做运行决策。它需要至少输出：

- `decision`: `reply` 或 `silence`
- `relation_delta`
- `persona_patch`
- `tag_ops`
- `internal_thought`
- `next_wakeup_hint`

这一步决定的是“角色此刻怎么想”，而不是“角色说什么”。

### 7.5 Generator Node

如果 Meta 决定 `reply`，才进入 Generator：

- 组织系统 Prompt
- 组装角色 Prompt
- 拼接过滤后的历史消息
- 拼接记忆片段和内部思考
- 连接上游模型
- 流式产生文本
- 按 chunk 持续广播给前端

### 7.6 Scheduler Node

这一步负责处理“本轮之后会发生什么”，包括：

- 是否创建新的 `WakeupTask`
- 是否触发后置压缩
- 是否在 Pull / Merge 后追加总结任务

当 `auto_compaction_enabled` 且消息窗口超过阈值时，应自动排入 `compaction` durable job；Pull / Merge 成功后也应补一个后置 compaction。

### 7.7 Side Effects

统一副作用层负责：

- 保存助手消息
- 持久化新的 `SessionState`
- 写入 `MemoryChunk`
- 记录 `AuditRun / Step / Artifact`
- 标记 `DispatchJob` 成功或失败

若当前存在启用中的 embedding provider，则 `MemoryChunk` 写入后还应生成并保存对应 `MemoryEmbedding`，再回填 `embedding_ref`。如果没有启用项，则只保留非向量记忆链路。

推荐的核心伪代码如下：

```python
async def run_chat_runtime(cocoon_id: str, ws_manager: ConnectionManager):
    state = get_session_state(cocoon_id)
    recent_msgs = get_messages_by_tags(cocoon_id, state.active_tags_json)
    long_term_memories = vector_db.query(
        ...,
        filter={"tags": {"$in": state.active_tags_json}},
    )

    meta_output = await run_meta_cognition(recent_msgs, long_term_memories)

    update_session_state(cocoon_id, meta_output.relation_delta)
    await ws_manager.broadcast(
        cocoon_id,
        {
            "type": "state_patch",
            "relation_score": new_score,
            "active_tags": new_tags,
        },
    )

    if meta_output.decision == "silence":
        return

    await ws_manager.broadcast(
        cocoon_id,
        {"type": "reply_started", "action_id": action_id},
    )

    full_reply = ""
    async for chunk in stream_llm_response(prompt_context, meta_output.internal_thought):
        full_reply += chunk
        await ws_manager.broadcast(
            cocoon_id,
            {"type": "reply_chunk", "text": chunk},
        )

    save_assistant_message(cocoon_id, full_reply, tags=state.active_tags_json)
    await ws_manager.broadcast(
        cocoon_id,
        {"type": "reply_done", "final_message_id": saved_id},
    )
```

---

## 8. 一条完整对话链路

下面给出用户发送一条新消息时的完整后端链路。照着这条链路实现，就能打通系统的主路径。

### 8.1 阶段一：前端发起 HTTP 请求

前端调用：

- `POST /api/v1/cocoons/{id}/messages`

请求体包含：

- `content`
- `client_request_id`
- `timezone`

### 8.2 阶段二：路由层入队

路由层按如下顺序工作：

1. 校验用户是否有权访问该 Cocoon。
2. 用 `client_request_id` 做幂等检查。
3. 读取当前 `SessionState.active_tags_json`。
4. 以这些标签作为消息可见性边界，落一条用户消息。
5. 创建 `DispatchJob(event_type="chat")`。
6. 返回 `202 Accepted + action_id`。

典型路由伪代码：

```python
@router.post("/cocoons/{cocoon_id}/messages", status_code=202)
async def send_message(cocoon_id: str, payload: MessagePayload, db: Session):
    if db.query(Message).filter_by(client_request_id=payload.client_request_id).first():
        return {"accepted": True}

    state = db.query(SessionState).get(cocoon_id)
    new_msg = Message(
        role="user",
        content=payload.content,
        tags_json=state.active_tags_json,
    )
    db.add(new_msg)

    job = create_dispatch_job(cocoon_id, action="chat")
    db.commit()
    return {"accepted": True, "action_id": job.id}
```

### 8.3 阶段三：后台执行器拿锁

后台扫描器轮询或订阅 `DispatchJob`，执行时必须拿到 Cocoon 级锁，避免同一宇宙同时跑两条生成链。

至少要控制两类并发问题：

- 同一 Cocoon 同时多次提交
- 同一用户频繁重复点击发送

因此 `DispatchJob` 需要 `lock_key` 和 `debounce_until`。

### 8.4 阶段四：Context Builder 组装上下文

执行器拿到锁后，构建上下文包：

1. 加载 `Cocoon` 和 `Character`
2. 加载 `SessionState`
3. 读取最近 N 条可见消息
4. 根据活跃标签检索长期记忆
5. 生成 Prompt 所需的角色设定、系统设定和会话摘要

### 8.5 阶段五：Meta Node 先做决策

Meta Node 至少做四件事：

1. 判断本轮是否该回复
2. 计算关系分增减
3. 更新人格补丁与活跃标签
4. 决定是否安排下一次唤醒

如果决定沉默，则本轮不会出现 `reply_started`，但仍然会：

- 更新 `SessionState`
- 写审计
- 结束 Job

### 8.6 阶段六：WebSocket 开始流式回传

若本轮需要回复：

1. 广播 `reply_started`
2. 流式广播若干个 `reply_chunk`
3. 完成后广播 `reply_done`

广播是每个在线前端的共同事实源，因此 WS 事件必须尽量小而稳定，避免前端解析复杂对象树。

### 8.7 阶段七：副作用持久化

流式结束后，统一副作用层执行：

1. 写入助手消息
2. 写入或更新 `SessionState`
3. 把本轮沉淀为 `MemoryChunk`
4. 写入 `AuditRun / AuditStep / AuditArtifact`
5. 标记 Job 成功

### 8.8 阶段八：前端补偿与一致性

前端看到 `reply_done` 后，应将临时流式气泡固化到消息列表；若网络中断，则在恢复后重新拉取：

- 最新消息页
- 最新 `SessionState`
- 本轮 `AuditRun` 摘要

### 8.9 顺序图

```text
User -> HTTP POST /messages
Route -> DB: save user message
Route -> DB: create dispatch job
Route -> User: 202 Accepted(action_id)

Worker -> DB: claim job + lock cocoon
Worker -> Runtime: build context
Runtime -> VectorDB: query memories by tags
Runtime -> Meta: decide reply/silence + state patch
Runtime -> WS: state_patch
Runtime -> WS: reply_started
Runtime -> LLM: stream generation
LLM -> Runtime: reply_chunk*
Runtime -> WS: reply_chunk*
Runtime -> DB: save assistant message
Runtime -> DB: save memory + audit + session state
Runtime -> WS: reply_done
Runtime -> WS: final state_patch
Worker -> DB: mark job success
```

---

## 9. 修改消息与重试链路

### 9.1 修改消息

修改消息不是简单 `UPDATE messages.content`。完整语义应是：

1. 找到被编辑的用户消息。
2. 清理这条消息之后同轮产生的助手输出。
3. 清理与该轮关联的记忆、失败记录和审计。
4. 必要时恢复到对应检查点或轮次起点。
5. 创建 `DispatchJob(event_type="edit")`。
6. 重新进入统一运行时。

### 9.2 重试生成

重试的语义与编辑不同：

1. 保留原用户消息。
2. 删除最后一条失败或需重生的助手输出。
3. 清理该轮副作用。
4. 创建 `DispatchJob(event_type="retry")`。
5. 重新进入统一运行时。

### 9.3 为什么也必须走 HTTP 202 + WS

如果编辑和重试改走同步响应或单独 SSE，会重新引入两套协议与两套错误模型，导致：

- 前端状态机分裂
- 审计口径不一致
- 运行时无法统一成单一 `RuntimeEvent`

因此编辑和重试必须与普通对话保持同一协议模型。

---

## 10. 长期记忆与上下文压缩

### 10.1 记忆写入原则

长期记忆不应把整轮原文直接丢进向量库，而应生成更适合未来检索的记忆片段：

- 对话事实
- 关系状态变化
- 人设偏移
- 关键承诺或偏好
- Pull / Merge 产出的总结

### 10.2 检索原则

检索时至少同时考虑：

- `cocoon_id`
- 标签过滤
- 时间衰减或最近性
- 语义相似度
- `scope`

### 10.3 上下文压缩

当消息过长时，系统需要把早期消息压缩为摘要记忆，再从主上下文中移除原文。压缩通常在两个时机触发：

- 自动触发：达到上下文阈值
- 手动触发：用户或管理员主动执行

压缩的产物至少包含：

- 一条或多条 `summary` 型 `MemoryChunk`
- 一份可追踪的 `AuditArtifact`
- 可选的“被压缩区间”记录

### 10.4 双记忆服务的落地建议

即便仓库历史上保留了两类记忆实现，复刻时也应收敛为单一语义：

- `memory_service.py` 负责摘要与整理策略
- `vector_memory.py` 负责检索与 embedding 存储

二者可以共存，但外部语义必须保持统一。

---

## 11. 主动唤醒（Wakeup）

### 11.1 核心目标

主动唤醒让角色不只在用户发言后才运行，而是在未来某个时间点主动“想起一件事”并决定要不要发言。

### 11.2 任务结构

`WakeupTask` 至少需要：

- `id`
- `cocoon_id`
- `run_at`
- `reason`
- `payload_json`
- `status`

### 11.3 执行链路

1. 后台扫描器按分钟扫描到期任务。
2. 为到期任务创建 `RuntimeEvent(event_type="wakeup")`。
3. 运行时加载上下文和心智状态。
4. Meta Node 判断：
   - 直接回复
   - 保持沉默
   - 重新安排下一次唤醒
5. 若需要回复，则同样通过 WS 推送给在线前端。

Wakeup 不是独立子系统，而是统一运行时的一种事件类型。

---

## 12. Pull 与 Merge

### 12.1 Pull：向下吸收

Pull 表示目标 Cocoon 吸收祖先的新知识。它通常用于“主线更新了设定，支线需要同步”。

标准步骤：

1. 确定源 Cocoon 和目标 Cocoon。
2. 找到目标上次同步锚点之后，源侧新增的可见消息和记忆。
3. 根据标签和作用域构造候选集。
4. 用统一运行时执行 `event_type="pull"`。
5. 产出 Pull 总结，并写入目标的 `summary/pull` 记忆。
6. 更新同步水位。

### 12.2 Merge：向上回流

Merge 表示子分支把自己的新经验、关系变化和人格补丁回流到父分支。

标准步骤：

1. 确定源分支和目标主线。
2. 构造候选消息、记忆和状态增量。
3. 运行 `event_type="merge"`。
4. 让 Merge Reconciler 处理冲突：
   - Persona 冲突
   - 标签冲突
   - 关系分冲突
5. 把融合后的状态写回目标 Cocoon。
6. 记录 Merge 审计与总结记忆。

### 12.3 Pull 与 Merge 的本质

它们都不是“复制消息”，而是“用运行时把一个宇宙的知识重新投影到另一个宇宙里”。

因此必须依赖：

- 标签过滤
- 记忆总结
- 状态融合
- 审计追踪

对于 isolated tag，还必须把它当成硬边界：未绑定该 tag 的目标 Cocoon 不得看到相关 message 或 memory 候选。

---

## 13. Checkpoint 与 Rollback

### 13.1 Checkpoint

Checkpoint 用于在关键节点创建一个“可以安全回去”的锚点。它通常记录：

- `cocoon_id`
- `anchor_msg_id`
- `label`
- `created_at`

### 13.2 Rollback 语义

回滚时不要立刻物理删除消息，而应：

1. 把当前有效视图拨回 `anchor_msg_id`
2. 标记锚点之后的数据为待清理
3. 让前端重新按“当前有效视图”读取消息
4. 由后台清理器延迟删除物理数据及其附属审计

### 13.3 为什么要延迟清理

延迟清理可以解决三个问题：

- 允许误操作恢复
- 允许审计回看
- 避免大事务下的锁竞争和删除风暴

---

## 14. 审计与洞察体系

### 14.1 AuditRun

每次运行至少创建一条 `AuditRun`，记录：

- `operation_type`
- `action_id`
- `status`
- `trigger_event_uid`
- `started_at`
- `finished_at`

### 14.2 AuditStep

每个运行阶段一个 `AuditStep`，建议包含：

- `context_builder`
- `meta_node`
- `generator_node`
- `scheduler_node`
- `side_effects`

### 14.3 AuditArtifact

每个阶段产出的关键材料都可以作为 `Artifact` 保存：

- 检索到的记忆列表
- 最终 Prompt
- Meta 结构化输出
- 模型原始返回
- 压缩结果
- Merge 冲突报告

当前实现建议至少稳定支持以下 artifact kind：

- `memory_retrieval`
- `provider_raw_output`
- `side_effects_result`
- `compaction_result`
- `merge_conflict_report`
- `workflow_summary`

### 14.4 AuditLink

`AuditLink` 用于表达“哪个 Artifact 来源于哪个 Step 或另一个 Artifact”，这样前端才能把审计结果画成树或链。

### 14.5 Insights 面板依赖什么

只要审计链完整，就可以自然派生：

- Token 消耗
- 模型调用次数
- 唤醒次数
- Pull / Merge 成功率
- 失败轮次分布
- 关系分变化轨迹

---

## 15. API 面与实现约束

### 15.1 必需接口族

如果要复刻完整功能，至少需要以下 API 族：

- `auth`：登录、刷新、登出、当前用户
- `characters`：角色 CRUD 与 ACL
- `model_providers` / `embedding_providers`：上游模型与 embedding 提供方
- `tags`：标签管理
- `chat_groups`：群聊/分组
- `cocoons`：Cocoon CRUD、树查询、消息、WS 连接
- `cocoon_pulls` / `cocoon_merges`：同步任务
- `checkpoints`：检查点与回滚
- `audits` / `insights`：审计与洞察
- `admin/*`：后台管理

### 15.2 路由层的强约束

路由层只做：

- 鉴权
- 参数校验
- 轻量入队
- WS 连接管理

路由层不应：

- 自己拼 Prompt
- 自己调模型
- 自己做记忆检索
- 自己处理 Pull / Merge 融合

另外，路由层除了全局 permission 校验，还必须调用对象级授权服务，不能只凭接口权限决定 character、cocoon、message、memory、audit 的可见性。

---

## 16. 复刻系统的关键 Checklist

### 16.1 绝不能丢的设计点

1. 客户端触发动作统一为 `HTTP 202 + WebSocket`。
2. `ChatRuntime` 必须成为唯一执行内核。
3. `SessionState` 必须独立持久化。
4. 标签必须同时参与消息过滤和记忆过滤。
5. 审计必须做到 `Run -> Step -> Artifact -> Link`。
6. Pull / Merge 必须经由运行时，而不是直接复制数据。
7. Rollback 必须采用逻辑激活、延迟清理。

### 16.2 推荐实现顺序

1. 先建 `User / Character / Cocoon / SessionState / Message / Tag` 基础表。
2. 实现 `POST /messages -> DispatchJob -> WS reply_chunk` 的最短主链路。
3. 补齐 Meta Node 与 `state_patch`。
4. 接入向量记忆与上下文压缩。
5. 接入编辑、重试和失败轮次处理。
6. 接入 Wakeup。
7. 接入 Pull / Merge。
8. 最后补全 Checkpoint / Rollback 与 Audit / Insights。

---

## 17. 一句话总结

Cocoon-SIT 的后端本质上是一个“以 Cocoon 为容器、以 SessionState 为心智、以 Tag 为边界、以 ChatRuntime 为执行内核、以 WebSocket 为统一回流通道”的异步会话操作系统。
