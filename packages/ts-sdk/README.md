# `@cocoon-sit/ts-sdk`

TypeScript SDK for the Cocoon-SIT backend.

## Files

- `openapi.json`: exported OpenAPI contract from the backend.
- `src/generated.ts`: generated schema/types from `openapi.json`.
- `src/client.ts`: hand-written fetch client on top of generated schema types.

## Workflow

1. Export OpenAPI from the backend:
   - `cd backend`
   - `.\.venv\Scripts\python.exe -m app.main --dump-openapi`
2. Regenerate TypeScript types:
   - `cd packages/ts-sdk`
   - `.\node_modules\.bin\openapi-typescript.cmd .\openapi.json -o .\src\generated.ts`
3. Typecheck the SDK:
   - `.\node_modules\.bin\tsc.cmd -p .\tsconfig.json`

## Notes

- Prefer generated schema types from `src/generated.ts` over ad-hoc inline object types in `src/client.ts`.
- `src/client.ts` is the stable hand-written surface for frontend consumers.
