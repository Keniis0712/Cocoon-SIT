import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiJson: vi.fn(),
  apiCall: vi.fn(),
  makeCocoonWsUrl: vi.fn(),
}));

vi.mock("@/api/client", () => ({
  apiJson: mocks.apiJson,
  apiCall: mocks.apiCall,
  makeCocoonWsUrl: mocks.makeCocoonWsUrl,
}));

import { getCocoonMemories } from "@/api/cocoons";

describe("cocoons api adapters", () => {
  beforeEach(() => {
    mocks.apiJson.mockReset();
    mocks.apiCall.mockReset();
    mocks.makeCocoonWsUrl.mockReset();
    window.sessionStorage.clear();
  });

  it("does not fall back to raw tag ids when tag labels are empty", async () => {
    mocks.apiJson.mockResolvedValueOnce({
      items: [
        {
          id: "memory-a",
          cocoon_id: "cocoon-a",
          scope: "summary",
          content: "remember this",
          summary: "summary",
          tags_json: ["9db5465535d940fb9bc04cefc63ad139"],
          tag_labels: [],
          source_kind: "runtime_analysis",
          created_at: "2026-05-01T00:00:00Z",
        },
      ],
      overview: {
        total: 1,
        by_pool: { tree_private: 1 },
        by_type: { summary: 1 },
        by_status: { active: 1 },
        tag_cloud: [],
        word_cloud: [],
        importance_average: 0,
        confidence_average: 3,
      },
    });

    const result = await getCocoonMemories(1);

    expect(result.items[0].tags).toEqual([]);
    expect(result.items[0].tag_refs).toEqual(["9db5465535d940fb9bc04cefc63ad139"]);
  });
});
