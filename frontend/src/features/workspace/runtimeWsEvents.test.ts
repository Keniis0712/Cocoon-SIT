import { describe, expect, it, vi } from "vitest";

import { createRuntimeWsEventHandler } from "@/features/workspace/runtimeWsEvents";
import type { MessageRead } from "@/api/types/chat";

function message(id: number, role: string, content: string): MessageRead {
  return {
    id,
    message_uid: `msg-${id}`,
    cocoon_id: 1,
    chat_group_id: null,
    source_cocoon_id: null,
    origin_cocoon_id: null,
    sender_user_id: null,
    role,
    content,
    is_thought: false,
    visibility_level: 0,
    delivery_status: "done",
    processing_status: "done",
    reply_to_message_id: null,
    created_at: "2026-04-26T10:00:00Z",
    updated_at: null,
  };
}

describe("createRuntimeWsEventHandler", () => {
  it("updates runtime state when a reply starts", () => {
    const upsertMessage = vi.fn();
    const setStreamingAssistant = vi.fn();
    const applyStatePatch = vi.fn();

    const handleEvent = createRuntimeWsEventHandler({
      sessionKey: "cocoon:1",
      upsertMessage,
      setStreamingAssistant,
      appendStreamingAssistant: vi.fn(),
      applyStatePatch,
      setError: vi.fn(),
      reloadWorkspace: vi.fn(),
    });

    const userMessage = message(1, "user", "hello");
    handleEvent({
      type: "reply_started",
      user_message_id: 1,
      user_message: userMessage,
    });

    expect(upsertMessage).toHaveBeenCalledWith("cocoon:1", userMessage);
    expect(setStreamingAssistant).toHaveBeenCalledWith("cocoon:1", "");
    expect(applyStatePatch).toHaveBeenCalledWith("cocoon:1", {
      dispatchState: "running",
      dispatchReason: null,
    });
  });

  it("reloads workspace and wakeups when a reply finishes without a streamed message", async () => {
    const reloadWorkspace = vi.fn();
    const reloadWakeups = vi.fn();
    const setStreamingAssistant = vi.fn();
    const applyStatePatch = vi.fn();
    const scrollToBottom = vi.fn();

    const handleEvent = createRuntimeWsEventHandler({
      sessionKey: 7,
      upsertMessage: vi.fn(),
      setStreamingAssistant,
      appendStreamingAssistant: vi.fn(),
      applyStatePatch,
      setError: vi.fn(),
      reloadWorkspace,
      reloadWakeups,
      scrollToBottom,
    });

    handleEvent({ type: "reply_done", assistant_message: undefined as never });
    await Promise.resolve();

    expect(reloadWorkspace).toHaveBeenCalledTimes(1);
    expect(reloadWakeups).toHaveBeenCalledTimes(1);
    expect(setStreamingAssistant).toHaveBeenCalledWith(7, "");
    expect(applyStatePatch).toHaveBeenCalledWith(7, {
      dispatchState: "idle",
      dispatchReason: null,
    });
    expect(scrollToBottom).toHaveBeenCalledTimes(1);
  });

  it("records failures and invokes the failure callback", () => {
    const setStreamingAssistant = vi.fn();
    const setError = vi.fn();
    const applyStatePatch = vi.fn();
    const reloadWakeups = vi.fn();
    const onRoundFailed = vi.fn();

    const handleEvent = createRuntimeWsEventHandler({
      sessionKey: "room-9",
      upsertMessage: vi.fn(),
      setStreamingAssistant,
      appendStreamingAssistant: vi.fn(),
      applyStatePatch,
      setError,
      reloadWorkspace: vi.fn(),
      reloadWakeups,
      onRoundFailed,
    });

    handleEvent({
      type: "round_failed",
      failed_round_id: 4,
      stage: "generation",
      retryable: false,
      error_detail: "provider timeout",
      user_message_id: 2,
      created_at: "2026-04-26T10:00:00Z",
    });

    expect(setStreamingAssistant).toHaveBeenCalledWith("room-9", "");
    expect(setError).toHaveBeenCalledWith("room-9", "provider timeout");
    expect(applyStatePatch).toHaveBeenCalledWith("room-9", { dispatchState: "error" });
    expect(reloadWakeups).toHaveBeenCalledTimes(1);
    expect(onRoundFailed).toHaveBeenCalledWith("provider timeout");
  });

  it("stores queue metadata for debounced dispatches", () => {
    const applyStatePatch = vi.fn();

    const handleEvent = createRuntimeWsEventHandler({
      sessionKey: 12,
      upsertMessage: vi.fn(),
      setStreamingAssistant: vi.fn(),
      appendStreamingAssistant: vi.fn(),
      applyStatePatch,
      setError: vi.fn(),
      reloadWorkspace: vi.fn(),
    });

    handleEvent({
      type: "dispatch_queued",
      status: "debounced",
      reason: "user_typing",
      debounce_until: "2026-04-26T10:05:00Z",
    });

    expect(applyStatePatch).toHaveBeenCalledWith(12, {
      dispatchState: "debounced",
      dispatchReason: "user_typing",
      debounceUntil: "2026-04-26T10:05:00Z",
    });
  });
});
