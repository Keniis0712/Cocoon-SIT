FROM node:22-alpine

WORKDIR /workspace

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml /workspace/
COPY frontend/package.json frontend/tsconfig.json frontend/vite.config.ts frontend/index.html /workspace/frontend/
COPY packages/ts-sdk/package.json /workspace/packages/ts-sdk/

RUN pnpm install --filter @cocoon-sit/frontend... --frozen-lockfile

COPY . /workspace
