# Frontend Workspaces

Updated: 2026-04-19

## Targets

The frontend now supports two chat workspace targets:

- `cocoon`
- `chat-group`

They are peers at the routing level, not parent/child screens.

## Shared Concepts

Both workspace types use the same high-level runtime ideas:

- message timeline
- streaming assistant output
- dispatch state
- wakeup indicators
- websocket-driven updates
- shared chat session store shape

## Shared Building Blocks

- `store/useChatSessionStore.ts`
- `hooks/useRuntimeWs.ts`
- `api/adapters/messages.ts`
- `api/adapters/runtimeWs.ts`
- `features/workspace/utils.ts`
- `features/workspace/runtimeWsEvents.ts`

## Cocoon Workspace

Route:

- `/cocoons/:cocoonId`

Current composition:

- `pages/CocoonWorkspace.tsx`
- `features/cocoons/components/CocoonConversationPanel.tsx`
- `features/cocoons/components/CocoonSessionPanel.tsx`

Still owned by the page:

- loading cocoon/session/tag/model data
- retry/compaction/tag binding actions
- optimistic message send

## Chat-Group Workspace

Route:

- `/chat-groups/:roomId`

Current composition:

- `pages/ChatGroupWorkspace.tsx`
- `features/chat-groups/components/ChatGroupTimeline.tsx`
- `features/chat-groups/components/ChatGroupComposer.tsx`
- `features/chat-groups/components/ChatGroupSidebar.tsx`
- `features/chat-groups/components/ChatGroupDialogs.tsx`

Still owned by the page:

- room/member/message/state loading
- membership mutations
- optimistic message send

## Current Gap

The two pages now share runtime event handling, but still mirror each other in data-loading and mutation orchestration.

The next likely extraction point is feature-local hooks, for example:

- `useCocoonWorkspaceController`
- `useChatGroupWorkspaceController`
