# SDK Contract Sync

## Purpose

- Documents how backend API contract changes flow into `packages/ts-sdk`.
- Gives one repo-level workflow for exporting OpenAPI, regenerating types, and verifying drift.

## Source of Truth

- Backend routes and response models define the OpenAPI contract.
- `backend/app/main.py` provides the `--dump-openapi` export entrypoint.

## Sync Flow

1. Update backend routes, schemas, or response models.
2. Export the latest OpenAPI JSON into `packages/ts-sdk/openapi.json`.
3. Regenerate `packages/ts-sdk/src/generated.ts`.
4. Update `packages/ts-sdk/src/client.ts` to use generated schema types instead of fallback inline object shapes.
5. Run backend tests and SDK typecheck.

## Repo Commands

- `pnpm run sdk:sync`
  - Dumps OpenAPI from `backend/app/main.py`.
  - Regenerates `packages/ts-sdk/src/generated.ts`.
- `pnpm run sdk:typecheck`
  - Runs `tsc -p packages/ts-sdk/tsconfig.json`.
- `pnpm run sdk:verify`
  - Runs SDK typecheck and backend pytest coverage together.

## Generated and Hand-Written Boundaries

- `packages/ts-sdk/openapi.json`
  - Generated backend contract snapshot.
- `packages/ts-sdk/src/generated.ts`
  - Generated TypeScript schema/types. Do not hand-edit.
- `packages/ts-sdk/src/client.ts`
  - Stable hand-written fetch client.
  - Should prefer `components["schemas"]` aliases over ad-hoc inline return shapes.

## Notes

- This repo now treats `packages/ts-sdk/src/generated.ts` as a generated artifact, not a hand-edited file.
- Contract drift is most visible when a route still returns ad-hoc `dict` values instead of explicit schema models.
- When backend response types change, update the route response model first, then regenerate the SDK instead of patching `src/generated.ts` manually.
