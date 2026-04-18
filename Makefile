PYTHON ?= python

.PHONY: backend-dev backend-test backend-openapi sdk-generate sdk-typecheck sdk-sync sdk-verify frontend-dev

backend-dev:
	cd backend && uv run uvicorn app.main:app --reload

backend-test:
	cd backend && uv run pytest

backend-openapi:
	cd backend && uv run python -m app.main --dump-openapi

sdk-generate:
	corepack pnpm --dir packages/ts-sdk generate

sdk-typecheck:
	corepack pnpm --dir packages/ts-sdk typecheck

sdk-sync:
	cd backend && .\.venv\Scripts\python.exe -m app.main --dump-openapi
	corepack pnpm --dir packages/ts-sdk generate

sdk-verify:
	corepack pnpm --dir packages/ts-sdk typecheck
	cd backend && .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests

frontend-dev:
	corepack pnpm --dir frontend dev
