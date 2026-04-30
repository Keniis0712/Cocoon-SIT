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
- `features/workspace/useWorkspaceMessagingController.ts`

## Cocoon Workspace

Route:

- `/cocoons/:cocoonId`

Current composition:

- `pages/CocoonWorkspace.tsx`
- `features/cocoons/components/CocoonConversationPanel.tsx`
- `features/cocoons/components/CocoonSessionPanel.tsx`
- `features/cocoons/hooks/useCocoonWorkspaceController.ts`

Still owned by the controller hook:

- loading cocoon/session/tag/model data
- retry/compaction/tag binding actions
- cocoon-specific websocket recovery behavior

## Chat-Group Workspace

Route:

- `/chat-groups/:roomId`

Current composition:

- `pages/ChatGroupWorkspace.tsx`
- `features/chat-groups/components/ChatGroupTimeline.tsx`
- `features/chat-groups/components/ChatGroupComposer.tsx`
- `features/chat-groups/components/ChatGroupSidebar.tsx`
- `features/chat-groups/components/ChatGroupDialogs.tsx`
- `features/chat-groups/hooks/useChatGroupWorkspaceController.ts`

Still owned by the controller hook:

- room/member/message/state loading
- membership mutations
- chat-group-specific websocket recovery behavior

## Current State

The two pages now delegate orchestration into feature-local controller hooks:

- `useCocoonWorkspaceController`
- `useChatGroupWorkspaceController`

The pages are mostly view composition, while the shared send/store path lives in `useWorkspaceMessagingController`.

## Remaining Gap

Target-specific resource loading is still separate by design. If another workspace target is introduced later, the next extraction point is a thinner shared data loader contract on top of the current messaging controller.
