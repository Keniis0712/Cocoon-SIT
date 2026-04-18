import { create } from "zustand";

import type { MessageRead } from "@/api/types";

type SessionState = {
  messages: MessageRead[];
  streamingAssistant: string;
  relationScore: number | null;
  personaJson: Record<string, unknown>;
  activeTags: string[];
  currentModelId: number | null;
  dispatchState: string;
  dispatchReason: string | null;
  isUserTyping: boolean;
  lastError: string | null;
};

type ChatSessionStore = {
  sessions: Record<number, SessionState>;
  ensureSession: (cocoonId: number) => void;
  resetSession: (cocoonId: number) => void;
  setMessages: (cocoonId: number, messages: MessageRead[]) => void;
  prependMessages: (cocoonId: number, messages: MessageRead[]) => void;
  upsertMessage: (cocoonId: number, message: MessageRead) => void;
  setStreamingAssistant: (cocoonId: number, value: string) => void;
  appendStreamingAssistant: (cocoonId: number, value: string) => void;
  applyStatePatch: (
    cocoonId: number,
    patch: {
      relationScore?: number | null;
      personaJson?: Record<string, unknown>;
      activeTags?: string[];
      currentModelId?: number | null;
      dispatchState?: string;
      dispatchReason?: string | null;
    },
  ) => void;
  setTyping: (cocoonId: number, isTyping: boolean) => void;
  setError: (cocoonId: number, error: string | null) => void;
};

const EMPTY_SESSION: SessionState = {
  messages: [],
  streamingAssistant: "",
  relationScore: null,
  personaJson: {},
  activeTags: [],
  currentModelId: null,
  dispatchState: "idle",
  dispatchReason: null,
  isUserTyping: false,
  lastError: null,
};

function sortMessages(items: MessageRead[]) {
  return [...items].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime() || a.id - b.id,
  );
}

function mergeMessages(existing: MessageRead[], nextItems: MessageRead[]) {
  const map = new Map<number, MessageRead>();
  for (const item of existing) {
    map.set(item.id, item);
  }
  for (const item of nextItems) {
    map.set(item.id, item);
  }
  return sortMessages([...map.values()]);
}

export const useChatSessionStore = create<ChatSessionStore>((set, get) => ({
  sessions: {},
  ensureSession: (cocoonId) =>
    set((state) => ({
      sessions: state.sessions[cocoonId]
        ? state.sessions
        : { ...state.sessions, [cocoonId]: { ...EMPTY_SESSION } },
    })),
  resetSession: (cocoonId) =>
    set((state) => ({
      sessions: { ...state.sessions, [cocoonId]: { ...EMPTY_SESSION } },
    })),
  setMessages: (cocoonId, messages) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [cocoonId]: {
          ...(state.sessions[cocoonId] || EMPTY_SESSION),
          messages: sortMessages(messages),
        },
      },
    })),
  prependMessages: (cocoonId, messages) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [cocoonId]: {
          ...(state.sessions[cocoonId] || EMPTY_SESSION),
          messages: mergeMessages(state.sessions[cocoonId]?.messages || [], messages),
        },
      },
    })),
  upsertMessage: (cocoonId, message) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [cocoonId]: {
          ...(state.sessions[cocoonId] || EMPTY_SESSION),
          messages: mergeMessages(state.sessions[cocoonId]?.messages || [], [message]),
        },
      },
    })),
  setStreamingAssistant: (cocoonId, value) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [cocoonId]: {
          ...(state.sessions[cocoonId] || EMPTY_SESSION),
          streamingAssistant: value,
        },
      },
    })),
  appendStreamingAssistant: (cocoonId, value) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [cocoonId]: {
          ...(state.sessions[cocoonId] || EMPTY_SESSION),
          streamingAssistant: `${state.sessions[cocoonId]?.streamingAssistant || ""}${value}`,
        },
      },
    })),
  applyStatePatch: (cocoonId, patch) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [cocoonId]: {
          ...(state.sessions[cocoonId] || EMPTY_SESSION),
          relationScore: patch.relationScore ?? state.sessions[cocoonId]?.relationScore ?? null,
          personaJson: patch.personaJson ?? state.sessions[cocoonId]?.personaJson ?? {},
          activeTags: patch.activeTags ?? state.sessions[cocoonId]?.activeTags ?? [],
          currentModelId: patch.currentModelId ?? state.sessions[cocoonId]?.currentModelId ?? null,
          dispatchState: patch.dispatchState ?? state.sessions[cocoonId]?.dispatchState ?? "idle",
          dispatchReason: patch.dispatchReason ?? state.sessions[cocoonId]?.dispatchReason ?? null,
        },
      },
    })),
  setTyping: (cocoonId, isTyping) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [cocoonId]: {
          ...(state.sessions[cocoonId] || EMPTY_SESSION),
          isUserTyping: isTyping,
        },
      },
    })),
  setError: (cocoonId, error) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [cocoonId]: {
          ...(state.sessions[cocoonId] || EMPTY_SESSION),
          lastError: error,
        },
      },
    })),
}));

export function getChatSession(cocoonId: number) {
  return getOrCreateSession(cocoonId);
}

function getOrCreateSession(cocoonId: number) {
  const current = useChatSessionStore.getState().sessions[cocoonId];
  if (current) {
    return current;
  }
  useChatSessionStore.getState().ensureSession(cocoonId);
  return useChatSessionStore.getState().sessions[cocoonId] || { ...EMPTY_SESSION };
}
