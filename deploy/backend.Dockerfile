FROM python:3.12-slim AS backend-base

WORKDIR /app

RUN pip install uv

COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/uv.lock /app/uv.lock
RUN uv sync --frozen || uv sync

COPY backend /app

FROM node:22-alpine AS frontend-build

WORKDIR /workspace

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml /workspace/
COPY frontend/package.json frontend/tsconfig.json frontend/vite.config.ts frontend/index.html /workspace/frontend/
COPY packages/ts-sdk/package.json /workspace/packages/ts-sdk/
RUN pnpm install --frozen-lockfile

COPY frontend /workspace/frontend
COPY packages /workspace/packages
RUN pnpm --dir frontend build

FROM backend-base AS api-runtime

COPY --from=frontend-build /workspace/frontend/dist /app/frontend_dist

EXPOSE 8000

FROM backend-base AS worker-runtime
