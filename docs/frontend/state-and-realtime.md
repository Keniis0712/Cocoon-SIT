# Frontend State And Realtime

Updated: 2026-04-19

## Session Store

`store/useChatSessionStore.ts` is the shared runtime state container for cocoon and chat-group chat sessions.

It currently tracks:

- messages
- streaming assistant text
- relation score
- persona JSON
- active tags
- current model ID
- current wakeup task ID
- dispatch state and reason
- debounce timestamp
- typing state
- last error

## Session Keys

The store supports both numeric and string keys.

Examples:

- cocoon: numeric `cocoonId`
- chat-group: string key such as `chat-group:<roomId>`

This lets both workspace targets reuse one session model without forcing the route layer to fake identifier formats.

## Websocket Flow

Connection stack:

- `useRuntimeWs.ts`
- `useCocoonWs.ts`
- `useChatGroupWs.ts`

Event normalization:

- `api/adapters/runtimeWs.ts`

Event application:

- `features/workspace/runtimeWsEvents.ts`

This means the flow is now:

1. transport hook establishes websocket
2. API adapter normalizes backend event shape
3. workspace event helper applies store updates
4. page reacts only to target-specific reload/error behavior

## Current Strength

Realtime behavior is no longer page-local glue code. The shared path is now explicit enough to keep cocoon and chat-group behavior aligned.

`useWorkspaceMessagingController.ts` now centralizes:

- message input state
- typing telemetry
- optimistic send orchestration
- dispatch/debounce state patching
- first-load auto scroll behavior

## Current Risk

Pending message shape is shared, and optimistic send behavior is now shared, but transport-level send functions still remain target-specific. If more chat targets are introduced later, the next likely extraction is a unified workspace transport adapter interface.
