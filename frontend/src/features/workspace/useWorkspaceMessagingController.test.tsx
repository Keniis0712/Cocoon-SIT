import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatEnqueueResponse, MessageRead } from "@/api/types/chat";
import { useWorkspaceMessagingController } from "@/features/workspace/useWorkspaceMessagingController";
import { useChatSessionStore } from "@/store/useChatSessionStore";

function message(id: number, createdAt: string, overrides: Partial<MessageRead> = {}): MessageRead {
  return {
    id,
    message_uid: `msg-${id}`,
    cocoon_id: 1,
    chat_group_id: null,
    source_cocoon_id: null,
    origin_cocoon_id: null,
    sender_user_id: null,
    role: "user",
    content: `message-${id}`,
    is_thought: false,
    visibility_level: 0,
    delivery_status: "done",
    processing_status: "done",
    reply_to_message_id: null,
    created_at: createdAt,
    updated_at: null,
    ...overrides,
  };
}

function resetStore() {
  useChatSessionStore.setState({ sessions: {} });
}

describe("useWorkspaceMessagingController", () => {
  beforeEach(() => {
    resetStore();
    vi.useRealTimers();
  });

  it("computes optimistic send metadata and updates shared session state", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-26T12:00:05Z"));

    useChatSessionStore.getState().setMessages(1, [
      message(1, "2026-04-26T12:00:00Z"),
      message(2, "2026-04-26T12:00:03Z", { role: "assistant" }),
    ]);

    const sendMessage = vi.fn<
      (payload: Parameters<typeof useWorkspaceMessagingController>[0]["sendMessage"] extends (arg: infer T) => unknown ? T : never) => Promise<ChatEnqueueResponse>
    >().mockResolvedValue({
      accepted: true,
      dispatch_status: "queued",
      debounce_until: "2026-04-26T12:00:10Z",
      user_message: message(3, "2026-04-26T12:00:05Z", {
        message_uid: "pending-3",
        content: "hello world",
        delivery_status: "pending",
        processing_status: "queued",
      }),
    });

    const { result } = renderHook(() =>
      useWorkspaceMessagingController({
        sessionKey: 1,
        isLoading: false,
        timezone: "Asia/Shanghai",
        sendMessage,
        mapOptimisticMessage: (item) => ({ ...item, sender_user_id: "u-1" }),
      }),
    );

    act(() => {
      result.current.onMessageInputChange("hello world");
    });

    vi.advanceTimersByTime(1200);

    await act(async () => {
      await result.current.handleSendMessage();
    });

    expect(sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        content: "hello world",
        timezone: "Asia/Shanghai",
        locale: expect.any(String),
        idle_seconds: 3,
        recent_turn_count: 2,
        typing_hint_ms: 1200,
      }),
    );
    expect(result.current.messageInput).toBe("");
    expect(result.current.isSending).toBe(false);
    expect(useChatSessionStore.getState().sessions["1"]).toMatchObject({
      dispatchState: "queued",
      debounceUntil: "2026-04-26T12:00:10Z",
      isUserTyping: false,
    });
    expect(useChatSessionStore.getState().sessions["1"].messages.at(-1)).toMatchObject({
      id: 3,
      content: "hello world",
      sender_user_id: "u-1",
    });
  });

  it("resets runtime session-local UI state when switching targets", async () => {
    const sendMessage = vi.fn().mockResolvedValue({
      accepted: true,
      dispatch_status: "idle",
      debounce_until: null,
      user_message: message(4, "2026-04-26T12:00:00Z"),
    });

    const { result } = renderHook(() =>
      useWorkspaceMessagingController({
        sessionKey: "chat-group:room-1",
        isLoading: false,
        timezone: "UTC",
        sendMessage,
      }),
    );

    act(() => {
      result.current.onMessageInputChange("draft");
      useChatSessionStore.getState().upsertMessage("chat-group:room-1", message(4, "2026-04-26T12:00:00Z"));
    });

    act(() => {
      result.current.resetRuntimeSession();
    });

    expect(result.current.messageInput).toBe("");
    expect(useChatSessionStore.getState().sessions["chat-group:room-1"]).toMatchObject({
      messages: [],
      streamingAssistant: "",
      dispatchState: "idle",
      lastError: null,
    });
  });
});
