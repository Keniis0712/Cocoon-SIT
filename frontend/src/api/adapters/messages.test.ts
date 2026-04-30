import { beforeEach, describe, expect, it, vi } from "vitest";

import { createPendingUserMessage, mapWorkspaceMessage } from "@/api/adapters/messages";

describe("message adapters", () => {
  beforeEach(() => {
    vi.useRealTimers();
    window.sessionStorage.clear();
  });

  it("maps workspace messages with retraction metadata", () => {
    const mapped = mapWorkspaceMessage({
      id: "message-1",
      cocoon_id: "cocoon-9",
      chat_group_id: "group-3",
      sender_user_id: "user-4",
      role: "assistant",
      content: "hidden thought",
      is_thought: true,
      is_retracted: true,
      retracted_at: "2026-04-26T11:00:00Z",
      retracted_by_user_id: "user-7",
      retraction_note: "policy cleanup",
      created_at: "2026-04-26T10:00:00Z",
    });

    expect(mapped.message_uid).toBe("message-1");
    expect(mapped.cocoon_id).toEqual(expect.any(Number));
    expect(mapped.chat_group_id).toEqual(expect.any(Number));
    expect(mapped.sender_user_id).toEqual(expect.any(String));
    expect(mapped.delivery_status).toBe("retracted");
    expect(mapped.processing_status).toBe("retracted");
    expect(mapped.retraction_note).toBe("policy cleanup");
    expect(mapped.updated_at).toBe("2026-04-26T11:00:00Z");
  });

  it("creates pending cocoon messages with a stable queued state", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-26T12:30:00Z"));

    const pending = createPendingUserMessage("action-1", "hello world", {
      kind: "cocoon",
      targetId: 42,
    });

    expect(pending.message_uid).toBe("pending:action-1");
    expect(pending.cocoon_id).toBe(42);
    expect(pending.chat_group_id).toBeNull();
    expect(pending.delivery_status).toBe("pending");
    expect(pending.processing_status).toBe("queued");
    expect(pending.created_at).toBe("2026-04-26T12:30:00.000Z");
  });

  it("creates pending chat-group messages without a cocoon id", () => {
    const pending = createPendingUserMessage("action-2", "team update", {
      kind: "chat-group",
      targetId: "room-alpha",
    });

    expect(pending.cocoon_id).toBeNull();
    expect(pending.chat_group_id).toEqual(expect.any(Number));
    expect(pending.role).toBe("user");
    expect(pending.content).toBe("team update");
  });
});
