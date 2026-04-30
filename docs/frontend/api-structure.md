# Frontend API Structure

Updated: 2026-04-19

## Summary

`frontend/src/api/` is the frontend boundary for backend contracts. Pages and features should consume domain wrappers instead of calling the SDK client directly.

## Current Layout

```text
frontend/src/api
|-- adapters/
|-- admin-plugins.ts
|-- admin-users.ts
|-- adminArtifacts.ts
|-- adminAudits.ts
|-- audits.ts
|-- characters.ts
|-- chatGroups.ts
|-- client.ts
|-- cocoons.ts
|-- embeddingProviders.ts
|-- groups.ts
|-- id-map.ts
|-- insights.ts
|-- invites.ts
|-- merges.ts
|-- plugins.ts
|-- prompts.ts
|-- providers.ts
|-- roles.ts
|-- settings.ts
|-- tags.ts
|-- types/
|-- types.ts
|-- user.ts
`-- wakeups.ts
```

## Responsibilities

### `client.ts`

Shared transport layer.

Owns:

- authenticated requests
- token-aware retry behavior
- websocket URL builders

### Domain files

Examples:

- `admin-plugins.ts`
- `cocoons.ts`
- `chatGroups.ts`
- `characters.ts`
- `providers.ts`
- `wakeups.ts`

These files should:

- call the SDK client
- normalize backend payloads into frontend shapes
- hide legacy ID mapping details

### `adapters/`

This folder is for reusable mapping logic that would otherwise be duplicated across domain wrappers.

Current example:

- `adapters/runtimeWs.ts`

This adapter now handles shared runtime websocket event normalization for both cocoon and chat-group targets.

### `types/`

The type split has started.

Current modules:

- `types/common.ts`
- `types/chat.ts`
- `types/chat-groups.ts`
- `types/catalog.ts`
- `types/providers.ts`
- `types/settings.ts`
- `types/prompts.ts`
- `types/cocoons.ts`
- `types/operations.ts`
- `types/audit.ts`
- `types/insights.ts`
- `types/access.ts`
- `types/plugins.ts`
- `types/wakeups.ts`

`types.ts` now primarily acts as a compatibility barrel. Most shared transport contracts already live in dedicated modules under `types/`.

## Recommended Direction

Next type split targets:

1. remaining page-level helper types that are still colocated outside `types/`
2. import-path cleanup for files that can safely move from `@/api/types` to direct domain modules
3. continued consolidation between workspace plugin APIs and admin plugin APIs where shared transport shapes overlap

## Notes

- New domain modules should stay dependency-light and only contain transport contracts.
- `types.ts` may import from split modules when unsplit contracts still reference shared shapes such as `CharacterRead`, `TagRead`, `ModelProviderRead`, or `AvailableModelRead`.
- New or touched call sites should prefer direct domain imports such as `@/api/types/catalog` or `@/api/types/cocoons`.
- `@/api/types` should remain available as a compatibility barrel, but it is no longer the preferred default for new code.
