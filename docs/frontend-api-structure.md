# Frontend API Structure

`frontend/src/api/` 现在按功能拆成了前端侧 API 模块，而不是让页面直接到处调用 SDK client。

## Core

- `client.ts`
  - 负责创建匿名/鉴权 client。
  - 负责统一的 `401 -> refresh token -> retry` 流程。
- `src/lib/env.ts`
  - 默认优先使用 `VITE_API_BASE_URL`。
  - 未配置时退回到 `window.location.origin`，配合 Vite dev proxy 走同源访问。

## Feature Modules

- `auth.ts`
  - 登录、登出、健康检查、当前用户加载。
- `dashboard.ts`
  - 仪表盘聚合读取。
- `access.ts`
  - 用户、角色、群组、邀请码相关操作。
- `catalog.ts`
  - 角色设定、provider、model、embedding、tag、prompt template。
- `workspace.ts`
  - cocoon、消息、memory、checkpoint、rollback、workspace WebSocket URL。
- `operations.ts`
  - wakeup、pull、merge、audit、artifact cleanup。
- `types.ts`
  - 页面和模块共享的前端侧 API 类型别名与聚合返回结构。

## Boundary

- Page / hook / component
  - 只依赖功能 API 模块，不直接拼 `apiCall((client) => client.xxx())`。
- Feature API module
  - 负责把页面需要的多接口读取整理成明确的聚合函数。
- `client.ts`
  - 作为唯一的 SDK 调用底座，集中处理 token 和重试。

## Verification

- `corepack pnpm --dir frontend lint`
- `corepack pnpm --dir frontend build`

## Dev Proxy

- `frontend/vite.config.ts`
  - 开发态把 `/api` 和对应的 WebSocket 升级请求代理到 `VITE_BACKEND_TARGET`。
  - 默认目标是 `http://127.0.0.1:8000`。
- 后端默认不再为 `5173` 开 CORS。
  - 如果需要跨域部署，显式配置 `COCOON_CORS_ORIGINS`。
