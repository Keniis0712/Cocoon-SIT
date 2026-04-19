# Frontend Structure

Updated: 2026-04-19

## Source Layout

```text
frontend/src
|-- api/
|-- components/
|-- features/
|-- hooks/
|-- lib/
|-- locales/
|-- pages/
|-- store/
|-- main.tsx
|-- router.tsx
`-- index.css
```

## Layer Boundaries

### `pages/`

Route-entry files only.

Pages should own:

- route params
- page-level loading and redirect decisions
- API composition
- websocket connection setup
- mutation handler wiring

Pages should avoid large presentational blocks when those blocks can live in `features/`.

### `features/`

Domain UI and page-local presentation extracted from route files.

Current slices:

- `features/chat-groups/components/*`
- `features/cocoons/components/*`
- `features/workspace/*`

This is the preferred place for:

- timeline panels
- side panels
- dialogs
- runtime event helpers shared by workspace pages

### `components/`

Cross-domain reusable UI and shell pieces.

Examples:

- `MainLayout.tsx`
- `app-sidebar.tsx`
- `PageFrame.tsx`
- `ui/*`

### `hooks/`

Reusable hooks that are not page-specific.

Examples:

- `useRuntimeWs.ts`
- `useCocoonWs.ts`
- `useChatGroupWs.ts`

### `store/`

Thin Zustand state layer.

Current stores:

- `useUserStore.ts`
- `useChatSessionStore.ts`

## Current Assessment

The structure is healthy enough to scale, but still in a transition phase:

- presentation is increasingly moving into `features/`
- route pages still own too much mutation orchestration
- API contracts are now mostly split into `api/types/*`, and new work should import from the narrowest domain module available
