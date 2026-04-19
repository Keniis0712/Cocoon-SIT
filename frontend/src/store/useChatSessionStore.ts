import { create } from "zustand";

import type { MessageRead } from "@/api/types/chat";

type SessionState = {
  messages: MessageRead[];
  streamingAssistant: string;
  relationScore: number | null;
  personaJson: Record<string, unknown>;
  activeTags: string[];
  currentModelId: number | null;
  currentWakeupTaskId: string | null;
  dispatchState: string;
  dispatchReason: string | null;
  debounceUntil: string | null;
  isUserTyping: boolean;
  lastError: string | null;
};

type SessionKey = string | number;

type ChatSessionStore = {
  sessions: Record<string, SessionState>;
  ensureSession: (sessionKey: SessionKey) => void;
  resetSession: (sessionKey: SessionKey) => void;
  setMessages: (sessionKey: SessionKey, messages: MessageRead[]) => void;
  prependMessages: (sessionKey: SessionKey, messages: MessageRead[]) => void;
  upsertMessage: (sessionKey: SessionKey, message: MessageRead) => void;
  setStreamingAssistant: (sessionKey: SessionKey, value: string) => void;
  appendStreamingAssistant: (sessionKey: SessionKey, value: string) => void;
  applyStatePatch: (
    sessionKey: SessionKey,
    patch: {
      relationScore?: number | null;
      personaJson?: Record<string, unknown>;
      activeTags?: string[];
      currentModelId?: number | null;
      currentWakeupTaskId?: string | null;
      dispatchState?: string;
      dispatchReason?: string | null;
      debounceUntil?: string | null;
    },
  ) => void;
  setTyping: (sessionKey: SessionKey, isTyping: boolean) => void;
  setError: (sessionKey: SessionKey, error: string | null) => void;
};

const EMPTY_SESSION: SessionState = {
  messages: [],
  streamingAssistant: "",
  relationScore: null,
  personaJson: {},
  activeTags: [],
  currentModelId: null,
  currentWakeupTaskId: null,
  dispatchState: "idle",
  dispatchReason: null,
  debounceUntil: null,
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

function keyOf(sessionKey: SessionKey) {
  return String(sessionKey);
}

export const useChatSessionStore = create<ChatSessionStore>((set, get) => ({
  sessions: {},
  ensureSession: (sessionKey) =>
    set((state) => ({
      sessions: state.sessions[keyOf(sessionKey)]
        ? state.sessions
        : { ...state.sessions, [keyOf(sessionKey)]: { ...EMPTY_SESSION } },
    })),
  resetSession: (sessionKey) =>
    set((state) => ({
      sessions: { ...state.sessions, [keyOf(sessionKey)]: { ...EMPTY_SESSION } },
    })),
  setMessages: (sessionKey, messages) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [keyOf(sessionKey)]: {
          ...(state.sessions[keyOf(sessionKey)] || EMPTY_SESSION),
          messages: sortMessages(messages),
        },
      },
    })),
  prependMessages: (sessionKey, messages) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [keyOf(sessionKey)]: {
          ...(state.sessions[keyOf(sessionKey)] || EMPTY_SESSION),
          messages: mergeMessages(state.sessions[keyOf(sessionKey)]?.messages || [], messages),
        },
      },
    })),
  upsertMessage: (sessionKey, message) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [keyOf(sessionKey)]: {
          ...(state.sessions[keyOf(sessionKey)] || EMPTY_SESSION),
          messages: mergeMessages(state.sessions[keyOf(sessionKey)]?.messages || [], [message]),
        },
      },
    })),
  setStreamingAssistant: (sessionKey, value) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [keyOf(sessionKey)]: {
          ...(state.sessions[keyOf(sessionKey)] || EMPTY_SESSION),
          streamingAssistant: value,
        },
      },
    })),
  appendStreamingAssistant: (sessionKey, value) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [keyOf(sessionKey)]: {
          ...(state.sessions[keyOf(sessionKey)] || EMPTY_SESSION),
          streamingAssistant: `${state.sessions[keyOf(sessionKey)]?.streamingAssistant || ""}${value || ""}`,
        },
      },
    })),
  applyStatePatch: (sessionKey, patch) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [keyOf(sessionKey)]: {
          ...(state.sessions[keyOf(sessionKey)] || EMPTY_SESSION),
          relationScore: patch.relationScore ?? state.sessions[keyOf(sessionKey)]?.relationScore ?? null,
          personaJson: patch.personaJson ?? state.sessions[keyOf(sessionKey)]?.personaJson ?? {},
          activeTags: patch.activeTags ?? state.sessions[keyOf(sessionKey)]?.activeTags ?? [],
          currentModelId: patch.currentModelId ?? state.sessions[keyOf(sessionKey)]?.currentModelId ?? null,
          currentWakeupTaskId:
            patch.currentWakeupTaskId ?? state.sessions[keyOf(sessionKey)]?.currentWakeupTaskId ?? null,
          dispatchState: patch.dispatchState ?? state.sessions[keyOf(sessionKey)]?.dispatchState ?? "idle",
          dispatchReason: patch.dispatchReason ?? state.sessions[keyOf(sessionKey)]?.dispatchReason ?? null,
          debounceUntil: patch.debounceUntil ?? state.sessions[keyOf(sessionKey)]?.debounceUntil ?? null,
        },
      },
    })),
  setTyping: (sessionKey, isTyping) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [keyOf(sessionKey)]: {
          ...(state.sessions[keyOf(sessionKey)] || EMPTY_SESSION),
          isUserTyping: isTyping,
        },
      },
    })),
  setError: (sessionKey, error) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [keyOf(sessionKey)]: {
          ...(state.sessions[keyOf(sessionKey)] || EMPTY_SESSION),
          lastError: error,
        },
      },
    })),
}));

export function getChatSession(sessionKey: SessionKey) {
  return getOrCreateSession(sessionKey);
}

function getOrCreateSession(sessionKey: SessionKey) {
  const current = useChatSessionStore.getState().sessions[keyOf(sessionKey)];
  if (current) {
    return current;
  }
  useChatSessionStore.getState().ensureSession(sessionKey);
  return useChatSessionStore.getState().sessions[keyOf(sessionKey)] || { ...EMPTY_SESSION };
}
