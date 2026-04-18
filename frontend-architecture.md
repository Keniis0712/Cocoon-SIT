# Cocoon-SIT 前端设计与实现说明（统一协议版）

## 0. 文档说明

本文档专门说明 Cocoon-SIT 前端的技术栈、工程组织、状态管理、统一通信模式与视觉风格。目标是让读者在不依赖原代码的前提下，也能据此重建当前前端。

本文档默认以后端统一协议为前提：

- 所有会触发模型生成的动作，都由 REST 接口异步入队。
- 所有实时结果与状态变化，都由单一 WebSocket 连接回流。
- 前端的状态管理必须尽量被动，尽量少在客户端重建业务逻辑。

---

## 1. 前端定位

### 1.1 不是聊天 App，而是 AI 工作台

前端不是一个轻量 IM 界面，而是一个“AI Admin Console + 角色工作台”的混合体。它要同时承载三类场景：

- 资产与资源管理
- 实时交互工作台
- 审计与洞察面板

因此前端的布局、导航和组件体系都应偏向后台系统，而不是偏向纯聊天产品。

### 1.2 前端的职责边界

前端应承担：

- 路由与鉴权
- 表单提交与 202 入队
- WebSocket 事件消费
- 轻量客户端状态管理
- 视觉呈现与交互反馈

前端不应承担：

- 对话编排逻辑
- Prompt 拼装
- 心智计算
- 记忆检索
- Pull / Merge 的实际决策

这些都属于后端运行时职责。

---

## 2. 技术栈体系

### 2.1 核心框架

- `React 19`
- `Vite 6`
- `TypeScript 5.8`

React 负责页面与状态协作，Vite 负责开发体验和构建，TypeScript 保证接口契约和组件边界清晰。

### 2.2 状态管理

- `Zustand 5`

项目坚持轻量、本地化的状态管理风格，不引入重量级全局状态框架。状态按领域拆分，优先贴近页面使用场景。

### 2.3 UI 与样式

- `Tailwind CSS 4`
- `shadcn/ui`
- `Radix UI`
- `Lucide Icons`

这套组合的好处是：

- 设计令牌清晰
- 组件基础扎实
- 方便做工作台风格的高密度布局
- 可以在不脱离设计系统的前提下做出有辨识度的 UI

### 2.4 通信与基础设施

- `Axios`：REST API
- `Native WebSocket`：实时事件
- `i18next`：国际化
- `sonner`：全局 Toast
- `ECharts`：洞察面板图表

---

## 3. 工程组织

### 3.1 目录分层

前端建议保持以下目录结构：

- `frontend/src/api/`：接口封装与类型定义
- `frontend/src/components/`：布局与通用组件
- `frontend/src/hooks/`：通用 Hook
- `frontend/src/lib/`：工具函数
- `frontend/src/locales/`：多语言资源
- `frontend/src/pages/`：页面级组件
- `frontend/src/store/`：Zustand Store
- `frontend/src/index.css`：全局设计令牌与主题样式
- `frontend/src/router.tsx`：路由树

### 3.2 页面分层

页面可以分为三类：

1. 资源/资产管理页
2. 交互工作台
3. 审计与洞察页

推荐页面族如下：

- `/login`
- `/cocoons`
- `/cocoons/:id`
- `/cocoons/:id/memory`
- `/characters`
- `/tags`
- `/providers`
- `/embedding-providers`
- `/groups`
- `/users`
- `/settings`
- `/audits`
- `/insights`
- `/merges`

### 3.3 组件层次

建议保留三层组件：

- 页面骨架组件：`MainLayout`、`AppSidebar`、`PageFrame`
- 页面级组件：`CocoonWorkspace`、`AuditsWorkbench` 等
- 通用原子组件：按钮、输入框、卡片、表格、弹层、Badge

---

## 4. 状态管理策略（Zustand）

统一通信后，前端状态可以收敛得非常干净。核心只需要两个主 Store。

### 4.1 `useUserStore`

它负责全局身份状态：

- 当前用户信息
- Access Token / Refresh Token
- 基础权限信息
- 登录态恢复

实现建议：

- 使用 `persist` 中间件写入 `localStorage`
- Axios 拦截器遇到 `401` 时清空 Store
- 清空后统一跳转到 `/login`

### 4.2 `useChatSessionStore`

它是工作台心脏，但仍应保持克制。建议按 `cocoonId` 切片管理单个会话运行时。

核心状态：

- `messages`
- `streamingAssistant` 或 `streamingText`
- `relationScore`
- `personaJson`
- `activeTags`
- `isRoundRunning`

更新来源：

- 用户输入会直接更新本地输入框
- 自己发出的用户消息可乐观插入
- 助手输出与状态变更只接受 WS 事件驱动

推荐的最小 Store 结构如下：

```ts
import { create } from "zustand";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface ChatSessionState {
  messages: ChatMessage[];
  streamingText: string;
  relationScore: number;
  activeTags: string[];
  initMessages: (msgs: ChatMessage[]) => void;
  appendChunk: (text: string) => void;
  commitStreaming: (msgId: string) => void;
  patchState: (score: number, tags: string[]) => void;
}

export const useChatSessionStore = create<ChatSessionState>((set) => ({
  messages: [],
  streamingText: "",
  relationScore: 0,
  activeTags: [],
  initMessages: (msgs) => set({ messages: msgs }),
  appendChunk: (text) =>
    set((s) => ({ streamingText: s.streamingText + text })),
  commitStreaming: (msgId) =>
    set((s) => ({
      messages: [
        ...s.messages,
        { id: msgId, role: "assistant", content: s.streamingText },
      ],
      streamingText: "",
    })),
  patchState: (score, tags) =>
    set({ relationScore: score, activeTags: tags }),
}));
```

### 4.3 状态设计原则

- 不要把运行时决策逻辑搬到前端。
- 不要把每种动作单独做一套状态机。
- 不要让 SSE、WS、轮询三套机制同时更新同一份会话状态。
- 让前端只承担“显示服务端已决定的事实”。

---

## 5. 统一通信与 API 层

### 5.1 行为触发：REST 异步入队

所有会触发模型执行的动作都通过 Axios 调用 REST 接口，接口统一返回 `202 Accepted`：

- 发送消息：`POST /cocoons/{id}/messages`
- 修改消息：`PATCH /cocoons/{id}/user_message`
- 重试回复：`POST /cocoons/{id}/reply/retry`

前端拿到 202 之后不等待结果，只记住 `action_id`，把“结果何时回来”交给 WebSocket。

### 5.2 状态监听：单一 WebSocket

用户进入工作台时建立唯一连接：

- `WS /api/v1/cocoons/{id}/ws`

这个连接负责接收该 Cocoon 的所有实时事件。推荐事件如下：

```ts
type WsEvent =
  | { type: "dispatch_queued"; queue_length: number }
  | { type: "reply_started"; action_id: string }
  | { type: "reply_chunk"; text: string }
  | { type: "reply_done"; final_message_id: string }
  | { type: "state_patch"; relation_score: number; active_tags: string[] }
  | { type: "error"; reason: string };
```

### 5.3 事件消费规则

- `dispatch_queued`：可以更新“排队中”状态。
- `reply_started`：初始化流式气泡，进入“正在回复”状态。
- `reply_chunk`：持续拼接文本，并触发自动滚动。
- `reply_done`：把临时流式文本固化到消息数组。
- `state_patch`：更新关系分、活跃标签、人格摘要。
- `error`：终止本轮动画，弹出错误提示。

### 5.4 为什么前端必须统一到 WS

如果一部分动作走 SSE，一部分走 WS，会导致：

- 同一页面存在两套流式消费代码
- 错误、重连、超时处理不一致
- Store 需要适配两类事件形态
- 工作台状态变得难以推理

因此统一到 WS 不是表面上的“协议换皮”，而是降低整个前端复杂度的关键。

---

## 6. WebSocket 消费实现

建议封装一个工作台专用 Hook，例如 `useCocoonWS(cocoonId)`。它只做三件事：

- 建立连接
- 把服务端事件映射为 Store Action
- 在卸载时关闭连接

参考实现：

```ts
import { useEffect } from "react";
import { toast } from "sonner";
import { useChatSessionStore } from "./useChatSessionStore";

export function useCocoonWS(cocoonId: string) {
  const { appendChunk, commitStreaming, patchState } = useChatSessionStore();

  useEffect(() => {
    const ws = new WebSocket(
      `ws://127.0.0.1:8088/api/v1/cocoons/${cocoonId}/ws`,
    );

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case "reply_started":
          break;
        case "reply_chunk":
          appendChunk(data.text);
          break;
        case "reply_done":
          commitStreaming(data.final_message_id);
          break;
        case "state_patch":
          patchState(data.relation_score, data.active_tags);
          break;
        case "error":
          toast.error(data.reason);
          break;
      }
    };

    return () => ws.close();
  }, [cocoonId]);
}
```

实现时还应补上：

- 心跳或 `ping/pong`
- 异常关闭后的有限重连
- 连接恢复后的 REST 补偿拉取
- 组件卸载时的清理

---

## 7. 工作台页面实现

### 7.1 页面角色

`CocoonWorkspace` 是最核心的页面。它至少要完成以下职责：

- 初始化 WS 连接
- 拉取首屏消息和 Cocoon 基础信息
- 管理输入框与发送动作
- 渲染消息流
- 渲染流式输出气泡
- 渲染右侧状态面板

### 7.2 推荐交互模型

工作台建议采用三段式交互：

1. 左侧主区域显示消息气泡流
2. 右侧显示会话状态、标签、模型和关系信息
3. 底部显示输入区与操作按钮

### 7.3 发送消息的前端语义

发送时建议这样处理：

1. 用户点击发送
2. 本地输入框立即清空
3. 乐观插入用户气泡
4. 调用 `POST /messages`
5. 后续所有助手输出都交给 WS

参考实现：

```tsx
import { useState } from "react";
import axios from "axios";
import { useChatSessionStore } from "../store";
import { useCocoonWS } from "../hooks/useCocoonWS";

export default function CocoonWorkspace({ cocoonId }) {
  useCocoonWS(cocoonId);

  const { messages, streamingText, relationScore } = useChatSessionStore();
  const [input, setInput] = useState("");

  const handleSend = async () => {
    if (!input.trim()) return;

    const tempText = input;
    setInput("");

    useChatSessionStore.setState((s) => ({
      messages: [
        ...s.messages,
        { id: Date.now().toString(), role: "user", content: tempText },
      ],
    }));

    await axios.post(`/api/v1/cocoons/${cocoonId}/messages`, {
      content: tempText,
      client_request_id: crypto.randomUUID(),
    });
  };

  return (
    <div className="flex h-screen bg-neutral-900 text-neutral-100">
      <div className="flex-1 flex flex-col p-6 overflow-y-auto">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`p-4 mb-4 rounded-2xl max-w-2xl ${
              m.role === "user"
                ? "bg-neutral-800 ml-auto"
                : "bg-neutral-700/50 backdrop-blur"
            }`}
          >
            {m.content}
          </div>
        ))}

        {streamingText && (
          <div className="p-4 mb-4 rounded-2xl max-w-2xl bg-neutral-700/50 backdrop-blur border border-blue-500/30">
            {streamingText}
            <span className="inline-block w-2 h-4 ml-1 bg-blue-400 animate-pulse" />
          </div>
        )}
      </div>

      <div className="w-80 border-l border-neutral-800 p-6 flex flex-col gap-6">
        <div className="p-4 rounded-2xl bg-neutral-800/50">
          <h3 className="text-sm text-neutral-400 mb-2">Sync Status</h3>
          <div className="text-2xl font-mono text-cyan-400">
            Score: {relationScore}
          </div>
        </div>
      </div>
    </div>
  );
}
```

### 7.4 修改消息与重试在前端的实现原则

尽管动作不同，前端语义必须保持一致：

- 修改消息：调用 `PATCH /user_message`，等待同一 WS 连接回流
- 重试生成：调用 `POST /reply/retry`，等待同一 WS 连接回流

前端不应为编辑和重试创建另一套流式接收器。

---

## 8. UI 架构与布局基元

### 8.1 `MainLayout`

这是整个后台工作区的骨架，应包含：

- 顶层容器
- 左侧导航栏
- 主内容区
- 顶部上下文信息或操作位

### 8.2 `AppSidebar`

侧边栏建议按功能分区：

- 工作区：Cocoons、Memory、Merges
- 资源区：Characters、Tags、Providers、Groups
- 管理区：Users、Settings、Audits、Insights

导航项的可见性应由当前用户权限决定，而不是写死在前端。

### 8.3 `PageFrame`

管理型页面建议统一使用 `PageFrame`：

- 提供一致的标题区
- 提供 Sticky 操作栏
- 提供列表/表单区的统一边距

这样所有后台页会自然形成一个统一的管理系统语言。

### 8.4 `CocoonWorkspace`

它不应被做成一个“普通聊天页”，而应是一个工作台：

- 消息流是主舞台
- 右侧状态面板是副舞台
- 顶部可以挂运行状态、模型、标签切换
- 底部输入区尽量固定，保证长对话时操作稳定

---

## 9. 视觉设计语言

### 9.1 风格定位

系统建议采用“现代 AI Admin Console”的视觉方向，而不是默认的 SaaS 白底卡片风。

关键词：

- 大圆角
- 毛玻璃
- 中性灰基底
- 渐变氛围背景
- 工业感标题字体
- 稳定但有辨识度的配色

### 9.2 颜色系统

推荐使用基于 `OKLCH` 的中性调色盘作为主基底，再用少量强调色做状态提示。

建议：

- 背景与边框用中性灰系
- 成功、错误、警告、信息用少量语义色
- 工作台背景使用柔和的径向渐变增强空间感

不要把页面做成纯平、纯白、纯黑三块色带的组合。

### 9.3 字体系统

建议双字体方案：

- 正文字体：`Noto Sans`
- 标题字体：`Geist`

这样可以同时得到：

- 中文场景下更稳定的正文阅读体验
- 管理台标题的现代工业感

### 9.4 容器语言

容器应大量使用：

- `rounded-2xl`
- `rounded-3xl`
- `backdrop-blur`
- 半透明描边

这样工作台会更像“同一空间中的多个悬浮面板”，而不是传统表单页面。

### 9.5 动效风格

动效应克制但明确：

- 页面进入时轻微渐入
- 流式回复使用打字式更新
- Toast 用于错误和成功反馈
- 不要为了“炫”而让所有卡片都漂浮或抖动

---

## 10. 资源管理页、工作台与洞察页

### 10.1 资源管理页

典型页面：

- `Cocoons`
- `Characters`
- `Tags`
- `Providers`
- `Embedding Providers`
- `Groups`
- `Users`

这些页面以树、表格、筛选和表单为主，重点是：

- 信息密度
- 批量操作效率
- 权限可见性

### 10.2 交互工作台

典型页面：

- `CocoonWorkspace`
- `CocoonMemoryPage`

这些页面以实时性和上下文连续性为主，重点是：

- 实时事件消费
- 长消息列表渲染
- 输入体验
- 状态面板联动

### 10.3 洞察与审计页

典型页面：

- `Audits`
- `AuditsWorkbench`
- `Insights`

这些页面主要消费结构化后端数据，推荐使用：

- 时间轴
- 指标卡
- 图表
- 可展开的树状审计节点

`ECharts` 适合处理：

- 调用量趋势
- Token 消耗
- 唤醒分布
- 成功率与失败率

---

## 11. 鉴权、国际化与主题

### 11.1 鉴权

建议使用：

- Axios 请求拦截器自动附带 Token
- 响应拦截器统一处理 `401`
- `useUserStore` 作为登录态单一来源
- 受保护路由统一做守卫

### 11.2 国际化

建议使用 `i18next` 统一管理页面文案，并优先为以下场景建立 key：

- 导航
- 表单标题
- 操作按钮
- 错误提示
- 审计面板字段名

### 11.3 主题

系统应支持深浅主题切换，但设计风格需要在两种主题下保持同一种气质，而不是亮色一个系统、暗色另一个系统。

---

## 12. 前端重建 Checklist

### 12.1 必须保留的事实

1. 前端必须统一到 `REST 202 + WebSocket`。
2. 会话状态必须主要由 WS 驱动，而不是客户端推演。
3. `useUserStore` 与 `useChatSessionStore` 足以覆盖核心状态。
4. 工作台必须是“消息流 + 状态面板”的双栏结构。
5. 视觉风格必须偏 AI 工作台，而不是通用表单后台。
6. 审计与洞察页必须独立成一个页面族。

### 12.2 推荐实现顺序

1. 初始化 Vite、Tailwind、shadcn/ui、主题与字体。
2. 打通登录链路和 `useUserStore`。
3. 封装 API Client 与统一错误处理。
4. 实现 `useChatSessionStore`。
5. 实现 `useCocoonWS` 和工作台最短链路。
6. 完成 Cocoon 工作台的双栏布局。
7. 补齐资源管理页。
8. 最后接审计与洞察面板。

---

## 13. 一句话总结

Cocoon-SIT 前端本质上是一个“以 React 工作台为外壳、以 Zustand 做轻状态、以 WebSocket 作为实时心跳、以 OKLCH 中性色与大圆角毛玻璃构建视觉语言”的 AI 管理控制台。
