import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiCall: vi.fn(),
}));

vi.mock("@/api/client", () => ({
  apiCall: mocks.apiCall,
}));

import { getSystemSettings, updateSystemSettings } from "@/api/settings";

describe("settings api adapters", () => {
  beforeEach(() => {
    mocks.apiCall.mockReset();
    window.sessionStorage.clear();
  });

  it("maps backend system settings into frontend ids and defaults", async () => {
    mocks.apiCall.mockImplementation(async (callback: (client: any) => Promise<unknown>) =>
      callback({
        getSystemSettings: () =>
          Promise.resolve({
            allow_registration: true,
            max_chat_turns: 12,
            allowed_model_ids: ["model-a"],
            default_max_context_messages: 24,
            default_auto_compaction_enabled: true,
            private_chat_debounce_seconds: 3,
            rollback_retention_days: 7,
            rollback_cleanup_interval_hours: 24,
            created_at: "2026-04-26T10:00:00Z",
            updated_at: "2026-04-26T10:00:00Z",
          }),
      }),
    );

    const result = await getSystemSettings();

    expect(result).toMatchObject({
      allow_registration: true,
      max_chat_turns: 12,
      group_chat_debounce_seconds: 0,
    });
    expect(result.allowed_model_ids).toEqual([1]);
  });

  it("serializes legacy model ids back to actual ids on update", async () => {
    mocks.apiCall.mockImplementationOnce(async (callback: (client: any) => Promise<unknown>) =>
      callback({
        getSystemSettings: () =>
          Promise.resolve({
            allow_registration: true,
            max_chat_turns: 12,
            allowed_model_ids: ["model-a"],
            default_max_context_messages: 24,
            default_auto_compaction_enabled: true,
            private_chat_debounce_seconds: 3,
            rollback_retention_days: 7,
            rollback_cleanup_interval_hours: 24,
            created_at: "2026-04-26T10:00:00Z",
            updated_at: "2026-04-26T10:00:00Z",
          }),
      }),
    );
    await getSystemSettings();
    mocks.apiCall.mockImplementationOnce(async (callback: (client: any) => Promise<unknown>) =>
      callback({
        updateSystemSettings: vi.fn(async (payload) => ({
          ...payload,
          allow_registration: false,
          max_chat_turns: 8,
          default_max_context_messages: 12,
          default_auto_compaction_enabled: false,
          private_chat_debounce_seconds: 5,
          group_chat_debounce_seconds: 6,
          rollback_retention_days: 3,
          rollback_cleanup_interval_hours: 12,
          created_at: "2026-04-26T10:00:00Z",
          updated_at: "2026-04-26T10:00:00Z",
        })),
      }),
    );

    const result = await updateSystemSettings({
      allow_registration: false,
      max_chat_turns: 8,
      allowed_model_ids: [1],
    });

    expect(result.allowed_model_ids).toEqual([1]);
    expect(mocks.apiCall).toHaveBeenCalled();
  });
});
