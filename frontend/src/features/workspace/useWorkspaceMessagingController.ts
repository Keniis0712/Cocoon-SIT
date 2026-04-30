import { useEffect, useMemo, useRef, useState, type RefObject } from "react";

import type { ChatEnqueueResponse, ChatRequest, MessageRead } from "@/api/types/chat";
import type { ChatSessionState } from "@/store/useChatSessionStore";
import { useChatSessionStore } from "@/store/useChatSessionStore";

type SessionKey = string | number;

type UseWorkspaceMessagingControllerOptions = {
  sessionKey: SessionKey;
  isLoading: boolean;
  timezone: string;
  currentUserId?: string | null;
  sendMessage: (payload: ChatRequest) => Promise<ChatEnqueueResponse>;
  mapOptimisticMessage?: (message: MessageRead) => MessageRead;
};

type WorkspaceMessagingController = {
  viewportRef: RefObject<HTMLDivElement | null>;
  session: ChatSessionState | null;
  visibleMessages: MessageRead[];
  messageInput: string;
  isSending: boolean;
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
  resetRuntimeSession: () => void;
  scrollToBottom: () => void;
  onMessageInputChange: (value: string) => void;
  handleSendMessage: () => Promise<void>;
};

function getVisibleMessages(items: MessageRead[]) {
  return items.filter((item) => !item.is_thought);
}

export function useWorkspaceMessagingController({
  sessionKey,
  isLoading,
  timezone,
  currentUserId = null,
  sendMessage,
  mapOptimisticMessage,
}: UseWorkspaceMessagingControllerOptions): WorkspaceMessagingController {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const typingStartedAtRef = useRef<number | null>(null);
  const hasAutoScrolledRef = useRef(false);
  const [messageInput, setMessageInput] = useState("");
  const [isSending, setIsSending] = useState(false);

  const session = useChatSessionStore((state) => state.sessions[String(sessionKey)] ?? null);
  const ensureSession = useChatSessionStore((state) => state.ensureSession);
  const resetSession = useChatSessionStore((state) => state.resetSession);
  const setMessages = useChatSessionStore((state) => state.setMessages);
  const prependMessages = useChatSessionStore((state) => state.prependMessages);
  const upsertMessage = useChatSessionStore((state) => state.upsertMessage);
  const setStreamingAssistant = useChatSessionStore((state) => state.setStreamingAssistant);
  const appendStreamingAssistant = useChatSessionStore((state) => state.appendStreamingAssistant);
  const applyStatePatch = useChatSessionStore((state) => state.applyStatePatch);
  const setTyping = useChatSessionStore((state) => state.setTyping);
  const setError = useChatSessionStore((state) => state.setError);

  const visibleMessages = useMemo(() => getVisibleMessages(session?.messages || []), [session?.messages]);

  useEffect(() => {
    if (!viewportRef.current) {
      return;
    }
    if (!isLoading && visibleMessages.length > 0 && !hasAutoScrolledRef.current) {
      requestAnimationFrame(() => {
        if (viewportRef.current) {
          viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
        }
      });
      hasAutoScrolledRef.current = true;
    }
  }, [isLoading, visibleMessages.length]);

  function scrollToBottom() {
    if (!viewportRef.current) {
      return;
    }
    viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
  }

  function resetRuntimeSession() {
    ensureSession(sessionKey);
    resetSession(sessionKey);
    hasAutoScrolledRef.current = false;
    typingStartedAtRef.current = null;
    setMessageInput("");
    setIsSending(false);
  }

  function onMessageInputChange(value: string) {
    if (!typingStartedAtRef.current) {
      typingStartedAtRef.current = Date.now();
    }
    setTyping(sessionKey, true);
    setMessageInput(value);
  }

  async function handleSendMessage() {
    if (!messageInput.trim() || isSending) {
      return;
    }

    const content = messageInput.trim();
    const now = Date.now();
    const lastMessageAt = visibleMessages.length
      ? new Date(visibleMessages[visibleMessages.length - 1].created_at).getTime()
      : null;
    const idleSeconds = lastMessageAt ? Math.max(0, Math.floor((now - lastMessageAt) / 1000)) : null;
    const typingHint = typingStartedAtRef.current ? Math.max(0, now - typingStartedAtRef.current) : null;

    setIsSending(true);
    setTyping(sessionKey, false);
    setError(sessionKey, null);
    try {
      const result = await sendMessage({
        content,
        client_request_id: window.crypto?.randomUUID?.() || `${Date.now()}`,
        client_sent_at: new Date(now).toISOString(),
        timezone,
        locale: navigator.language || null,
        idle_seconds: idleSeconds,
        recent_turn_count: visibleMessages.slice(-8).length,
        typing_hint_ms: typingHint,
      });
      upsertMessage(
        sessionKey,
        mapOptimisticMessage ? mapOptimisticMessage(result.user_message) : result.user_message,
      );
      applyStatePatch(sessionKey, {
        dispatchState: result.dispatch_status,
        dispatchReason: null,
        debounceUntil: result.debounce_until,
      });
      setMessageInput("");
      typingStartedAtRef.current = null;
      queueMicrotask(scrollToBottom);
    } finally {
      setIsSending(false);
    }
  }

  return {
    viewportRef,
    session,
    visibleMessages,
    messageInput,
    isSending,
    ensureSession,
    resetSession,
    setMessages,
    prependMessages,
    upsertMessage,
    setStreamingAssistant,
    appendStreamingAssistant,
    applyStatePatch,
    setTyping,
    setError,
    resetRuntimeSession,
    scrollToBottom,
    onMessageInputChange,
    handleSendMessage,
  };
}
