# Cocoon-SIT

[English](README.md) | 简体中文

Cocoon-SIT AI 工作台平台的 monorepo。

## 仓库结构

- `backend/`：FastAPI API、worker 运行时、持久化、prompt、审计、记忆、RBAC、插件
- `frontend/`：React/Vite 管理台与工作区前端
- `packages/ts-sdk/`：基于 OpenAPI 生成的 TypeScript SDK
- `plugins/`：本地示例插件与打包产物
- `deploy/`：Docker Compose、Dockerfile、环境模板、初始化脚本
- `docs/`：维护中的架构与实现说明

## 技术栈

### 后端

- FastAPI
- SQLAlchemy 2 + Alembic
- Postgres + pgvector
- Redis Streams + Pub/Sub
- Pydantic Settings
- 基于 Fernet 的 provider 密钥加密

### 前端

- React 19
- Vite 6
- TypeScript
- Zustand
- i18next

## 快速开始

1. 将 `deploy/.env.example` 复制为 `deploy/.env`，并按需修改配置。
2. 使用 `corepack pnpm install` 安装工作区依赖。
3. 使用 `pnpm run backend:dev` 启动后端 API。
4. 使用 `pnpm run backend:worker` 启动 worker。
5. 如果需要自定义后端地址，将 `frontend/.env.example` 复制为 `frontend/.env`。
6. 使用 `pnpm run frontend:dev` 启动前端。
7. 访问 `http://127.0.0.1:5173`，使用 `admin / admin` 登录。

生产环境前端默认走同源 API；本地开发通过 Vite dev proxy 转发 `/api`。

## Docker

### 接近生产的完整栈

- `docker compose -f deploy/docker-compose.yml up --build`
- 打包后的应用默认发布在 `http://127.0.0.1:8388`
- `api` 容器会在启动前执行 `alembic upgrade head`

### 开发栈

- `docker compose -f deploy/docker-compose.dev.yml up --build`
- 前端：`http://127.0.0.1:5173`
- 后端 API：`http://127.0.0.1:8000`

如果你之前跑过旧版 compose 定义，建议先执行 `docker compose ... down -v` 清理旧命名卷。

## SDK 同步

- 后端 API 变更后重新生成 TypeScript SDK：`pnpm run sdk:sync`
- 校验 SDK 类型和后端回归：`pnpm run sdk:verify`

后端侧 SDK 说明见 `docs/backend/sdk-contract.md`。

## 记忆与向量检索

- 系统允许存在多个 embedding provider 配置，但同一时刻只能启用一个。
- 即使没有启用 embedding provider，普通聊天和记忆链路仍可正常工作，只是跳过向量检索。
- 向量检索基于 Postgres `vector` 扩展。
- SQLite 仍是默认的本地开发和测试数据库。

实现说明见 `docs/vector-memory.md`。

## 测试

- 默认后端测试运行在 SQLite 和内存版 queue/backplane 适配器上。
- pgvector 集成测试是可选的，需要配置 `COCOON_PGVECTOR_TEST_DATABASE_URL`。
- 在 `backend/` 目录下可显式运行 pgvector 测试：`.\.venv\Scripts\python.exe -m pytest tests/integration/test_pgvector_memory.py -q`。

仓库根目录常用脚本：

- `pnpm run frontend:lint`
- `pnpm run frontend:test`
- `pnpm run backend:test`
- `pnpm run backend:test:api`
- `pnpm run backend:test:integration`
- `pnpm run backend:test:unit`
- `pnpm run frontend:build`
- `pnpm run lint`
- `pnpm run check`

## 当前功能面

仓库当前已经包含：

- cocoon 与 chat-group 两类工作区
- 统一的 `ChatRuntime` 运行时编排
- REST + WebSocket 实时链路
- 带版本修订的 prompt 模板管理
- 审计产物与 insights 面板
- 邀请码与额度管理
- 插件安装、运行时管理与工作区插件绑定
- 可选的向量记忆检索

## 说明

- 生产环境应通过 Docker Compose 使用 Postgres + Redis。
- Prompt 模板是全局生效的，每次保存都会生成不可变修订。
- 后端默认关闭 CORS，只有配置 `COCOON_CORS_ORIGINS` 时才会启用。
- worker 专属代码位于 `backend/app/worker/`。
- 当前维护中的实现说明都在 `docs/` 目录；仓库根目录曾经的架构草稿已移除，不应再作为现状依据。
