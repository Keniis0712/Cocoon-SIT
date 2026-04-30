import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiJson: vi.fn(),
}));

vi.mock("@/api/client", () => ({
  apiJson: mocks.apiJson,
}));

import { bindChatGroupTags, createTag, listTags, updateTag } from "@/api/tags";

describe("tags api adapters", () => {
  beforeEach(() => {
    mocks.apiJson.mockReset();
    window.sessionStorage.clear();
  });

  it("maps raw tag payloads into frontend tag records", async () => {
    mocks.apiJson.mockResolvedValueOnce([
      {
        id: "tag-a",
        tag_id: "focus",
        brief: "Focus mode",
        visibility: "private",
        is_system: false,
        visible_chat_group_ids: [],
        created_at: "2026-04-26T10:00:00Z",
      },
    ]);

    const result = await listTags();

    expect(result[0]).toMatchObject({
      id: 1,
      actual_id: "tag-a",
      name: "focus",
      visibility_mode: "private",
    });
  });

  it("serializes create and update requests using tag names and visibility", async () => {
    mocks.apiJson
      .mockResolvedValueOnce({
        id: "tag-a",
        tag_id: "focus",
        brief: "Focus mode",
        visibility: "group_acl",
        is_system: false,
        visible_chat_group_ids: ["room-1"],
        created_at: "2026-04-26T10:00:00Z",
      })
      .mockResolvedValueOnce({
        id: "tag-a",
        tag_id: "focus",
        brief: "Updated",
        visibility: "private",
        is_system: false,
        visible_chat_group_ids: [],
        created_at: "2026-04-26T10:00:00Z",
      });

    const created = await createTag({
      name: "focus",
      brief: "Focus mode",
      visibility_mode: "group_acl",
      visible_chat_group_ids: ["room-1"],
    });
    const updated = await updateTag(created.id, {
      brief: "Updated",
      visibility_mode: "private",
    });

    expect(mocks.apiJson).toHaveBeenNthCalledWith(
      1,
      "/tags",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          tag_id: "focus",
          brief: "Focus mode",
          visibility: "group_acl",
          is_isolated: false,
          meta_json: {},
          visible_chat_group_ids: ["room-1"],
        }),
      }),
    );
    expect(mocks.apiJson).toHaveBeenNthCalledWith(
      2,
      "/tags/tag-a",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          brief: "Updated",
          visibility: "private",
          is_isolated: true,
          meta_json: {},
          visible_chat_group_ids: undefined,
        }),
      }),
    );
    expect(updated.brief).toBe("Updated");
  });

  it("reconciles chat-group tags by binding missing tags and unbinding removed ones", async () => {
    mocks.apiJson
      .mockResolvedValueOnce([
        {
          id: "tag-a",
          tag_id: "focus",
          brief: "",
          visibility: "private",
          is_system: false,
          visible_chat_group_ids: [],
          created_at: "2026-04-26T10:00:00Z",
        },
        {
          id: "tag-b",
          tag_id: "system-tag",
          brief: "",
          visibility: "private",
          is_system: true,
          visible_chat_group_ids: [],
          created_at: "2026-04-26T10:00:00Z",
        },
      ])
      .mockResolvedValueOnce([
        { id: "binding-1", tag_id: "tag-b", created_at: "2026-04-26T10:00:00Z" },
      ])
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce([
        { id: "binding-1", tag_id: "tag-b", created_at: "2026-04-26T10:00:00Z" },
        { id: "binding-2", tag_id: "tag-a", created_at: "2026-04-26T10:00:00Z" },
      ]);

    const result = await bindChatGroupTags("room-1", [1]);

    expect(mocks.apiJson).toHaveBeenNthCalledWith(3, "/chat-groups/room-1/tags", {
      method: "POST",
      body: JSON.stringify({ tag_id: "tag-a" }),
    });
    expect(result.map((item) => item.actual_id)).toEqual(["tag-b", "tag-a"]);
  });
});
