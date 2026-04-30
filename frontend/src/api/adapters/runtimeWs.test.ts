import { describe, expect, it, vi } from "vitest";

import { mapRuntimeWsEvent } from "@/api/adapters/runtimeWs";

describe("mapRuntimeWsEvent", () => {
  it("normalizes chunk payloads and preserves flush state", () => {
    const mapped = mapRuntimeWsEvent({ type: "reply_chunk", text: "Hello", flush: 1 }, (value) => value);

    expect(mapped).toEqual({
      type: "reply_chunk",
      text: "Hello",
      delta: "Hello",
      flush: true,
    });
  });

  it("maps reply messages through the provided mapper", () => {
    const mapMessage = vi.fn((message: { id: number }) => ({ ...message, mapped: true }));

    const started = mapRuntimeWsEvent(
      {
        type: "reply_started",
        user_message_id: 7,
        user_message: { id: 7 },
      },
      mapMessage,
    );
    const done = mapRuntimeWsEvent(
      {
        type: "reply_done",
        assistant_message: { id: 8 },
      },
      mapMessage,
    );

    expect(started).toMatchObject({
      type: "reply_started",
      user_message: { id: 7, mapped: true },
    });
    expect(done).toMatchObject({
      type: "reply_done",
      assistant_message: { id: 8, mapped: true },
    });
    expect(mapMessage).toHaveBeenCalledTimes(2);
  });

  it("fills null wakeup ids and remaps model ids on state patches", () => {
    const mapped = mapRuntimeWsEvent(
      {
        type: "state_patch",
        relation_score: 52,
        persona_json: {},
        active_tags: ["focus"],
        current_model_id: "12",
      },
      (value) => value,
      {
        mapModelId: (modelId) => Number(modelId),
      },
    );

    expect(mapped).toMatchObject({
      type: "state_patch",
      relation_score: 52,
      active_tags: ["focus"],
      current_model_id: 12,
      current_wakeup_task_id: null,
    });
  });
});
