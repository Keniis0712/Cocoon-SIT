import type { MessageRead } from "@/api/types/chat";
import { getChatSession, useChatSessionStore } from "@/store/useChatSessionStore";
import { beforeEach, describe, expect, it } from "vitest";

function message(id: number, createdAt: string, content = `message-${id}`): MessageRead {
  return {
    id,
    message_uid: `msg-${id}`,
    cocoon_id: 1,
    chat_group_id: null,
    source_cocoon_id: null,
    origin_cocoon_id: null,
    sender_user_id: null,
    role: id % 2 === 0 ? "assistant" : "user",
    content,
    is_thought: false,
    visibility_level: 0,
    delivery_status: "delivered",
    processing_status: "done",
    reply_to_message_id: null,
    created_at: createdAt,
    updated_at: null,
  };
}

describe("useChatSessionStore", () => {
  beforeEach(() => {
    useChatSessionStore.setState({ sessions: {} });
  });

  it("creates default sessions on demand for both numeric and string keys", () => {
    const cocoonSession = getChatSession(1);
    const groupSession = getChatSession("chat-group:room-1");

    expect(cocoonSession.relationScore).toBe(50);
    expect(groupSession.dispatchState).toBe("idle");
    expect(Object.keys(useChatSessionStore.getState().sessions)).toEqual(["1", "chat-group:room-1"]);
  });

  it("sorts, prepends, and upserts messages without duplicates", () => {
    const store = useChatSessionStore.getState();
    store.ensureSession(1);
    store.setMessages(1, [message(2, "2026-04-26T10:00:02Z"), message(1, "2026-04-26T10:00:01Z")]);
    store.prependMessages(1, [message(0, "2026-04-26T10:00:00Z")]);
    store.upsertMessage(1, message(2, "2026-04-26T10:00:02Z", "updated"));

    expect(useChatSessionStore.getState().sessions["1"].messages.map((item) => item.id)).toEqual([0, 1, 2]);
    expect(useChatSessionStore.getState().sessions["1"].messages.at(-1)?.content).toBe("updated");
  });

  it("applies state patches while preserving unrelated values", () => {
    const store = useChatSessionStore.getState();
    store.ensureSession("chat-group:7");
    store.setStreamingAssistant("chat-group:7", "draft");
    store.applyStatePatch("chat-group:7", {
      relationScore: 88,
      activeTags: ["ops"],
      currentModelId: 3,
      dispatchState: "queued",
    });

    expect(useChatSessionStore.getState().sessions["chat-group:7"]).toMatchObject({
      streamingAssistant: "draft",
      relationScore: 88,
      activeTags: ["ops"],
      currentModelId: 3,
      dispatchState: "queued",
      currentWakeupTaskId: null,
    });
  });
});
