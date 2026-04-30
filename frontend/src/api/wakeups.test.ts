import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiJson: vi.fn(),
  resolveActualId: vi.fn(),
}));

vi.mock("@/api/client", () => ({
  apiJson: mocks.apiJson,
}));

vi.mock("@/api/id-map", () => ({
  resolveActualId: mocks.resolveActualId,
}));

import { listAuditWakeups, listChatGroupWakeups, listCocoonWakeups } from "@/api/wakeups";

describe("wakeups api adapters", () => {
  beforeEach(() => {
    mocks.apiJson.mockReset();
    mocks.resolveActualId.mockReset();
    mocks.resolveActualId.mockImplementation((_kind: string, id: number) => `actual-${id}`);
  });

  it("serializes audit wakeup filters into the query string", async () => {
    mocks.apiJson.mockResolvedValueOnce([]);

    await listAuditWakeups({
      status: "queued",
      only_ai: true,
      limit: 20,
      target_type: "cocoon",
      target_id: "actual-12",
    });

    expect(mocks.apiJson).toHaveBeenCalledWith(
      "/audits/wakeups?status=queued&only_ai=true&limit=20&target_type=cocoon&target_id=actual-12",
    );
  });

  it("maps cocoon wakeup requests through the legacy id resolver", async () => {
    mocks.apiJson.mockResolvedValueOnce([]);

    await listCocoonWakeups(12, {
      status: "failed",
      only_ai: true,
    });

    expect(mocks.resolveActualId).toHaveBeenCalledWith("cocoon", 12);
    expect(mocks.apiJson).toHaveBeenCalledWith(
      "/cocoons/actual-12/wakeups?status=failed&only_ai=true",
    );
  });

  it("builds chat-group wakeup paths without id remapping", async () => {
    mocks.apiJson.mockResolvedValueOnce([]);

    await listChatGroupWakeups("room-1", { limit: 5 });

    expect(mocks.apiJson).toHaveBeenCalledWith("/chat-groups/room-1/wakeups?limit=5");
  });
});
