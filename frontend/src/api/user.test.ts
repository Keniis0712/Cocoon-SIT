import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiCall: vi.fn(),
  apiJson: vi.fn(),
  createAnonymousClient: vi.fn(),
  getApiBaseUrl: vi.fn(),
  getErrorMessage: vi.fn(),
}));

vi.mock("@/api/client", () => ({
  apiCall: mocks.apiCall,
  apiJson: mocks.apiJson,
  createAnonymousClient: mocks.createAnonymousClient,
  getApiBaseUrl: mocks.getApiBaseUrl,
  getErrorMessage: mocks.getErrorMessage,
}));

import { buildSessionPatch, getPublicFeatures, login, me } from "@/api/user";

describe("user api adapters", () => {
  beforeEach(() => {
    for (const mock of Object.values(mocks)) {
      mock.mockReset();
    }
    window.sessionStorage.clear();
    mocks.getApiBaseUrl.mockReturnValue("https://example.test");
    mocks.getErrorMessage.mockImplementation((error: { message?: string }) => error.message || "unknown");
  });

  it("maps auth profile responses into a frontend me model", async () => {
    mocks.apiJson.mockResolvedValue({
      id: "user-1",
      username: "alice",
      email: "alice@example.com",
      role_id: "role-1",
      role_name: "operator",
      is_active: true,
      created_at: "2026-04-26T10:00:00Z",
      timezone: "Asia/Shanghai",
      permissions: {
        "audits:read": true,
        "providers:read": true,
        "providers:write": true,
      },
    });

    const result = await me();

    expect(result).toMatchObject({
      username: "alice",
      role: "operator",
      role_level: 1,
      can_audit: true,
      can_manage_providers: true,
      timezone: "Asia/Shanghai",
    });
    expect(typeof result.uid).toBe("string");
  });

  it("logs in by combining token and fetched profile data", async () => {
    const anonymousClient = {
      login: vi.fn().mockResolvedValue({
        access_token: "access-1",
        refresh_token: "refresh-1",
      }),
    };
    mocks.createAnonymousClient.mockReturnValue(anonymousClient);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        text: vi.fn().mockResolvedValue(
          JSON.stringify({
            id: "user-1",
            username: "alice",
            email: null,
            role_id: null,
            role_name: "admin",
            is_active: true,
            created_at: "2026-04-26T10:00:00Z",
            timezone: "UTC",
            permissions: { "users:write": true },
          }),
        ),
      }),
    );

    const result = await login("alice", "secret");

    expect(anonymousClient.login).toHaveBeenCalledWith({ username: "alice", password: "secret" });
    expect(fetch).toHaveBeenCalledWith(
      "https://example.test/api/v1/auth/me",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer access-1",
        }),
      }),
    );
    expect(result).toMatchObject({
      access_token: "access-1",
      refresh_token: "refresh-1",
      username: "alice",
      role: "admin",
    });
  });

  it("maps public features and exposes a session patch helper", async () => {
    mocks.createAnonymousClient.mockReturnValue({
      getPublicFeatures: vi.fn().mockResolvedValue({
        allow_registration: true,
        max_chat_turns: 12,
        allowed_models: [
          { id: "model-a", provider_id: "provider-a", model_name: "gpt-test" },
        ],
        rollback_retention_days: 7,
        rollback_cleanup_interval_hours: 24,
      }),
    });

    const features = await getPublicFeatures();
    const patch = buildSessionPatch({
      uid: "1",
      username: "alice",
      email: null,
      parent_uid: null,
      user_path: null,
      role: "admin",
      role_level: 0,
      can_audit: true,
      can_manage_system: true,
      can_manage_users: true,
      can_manage_prompts: true,
      can_manage_providers: true,
      timezone: "UTC",
      permissions: { "users:write": true },
      invite_quota_remaining: 5,
      invite_quota_unlimited: false,
      created_at: "2026-04-26T10:00:00Z",
    });

    expect(features.allow_registration).toBe(true);
    expect(features.allowed_models[0]).toMatchObject({
      provider_name: "",
      model_name: "gpt-test",
    });
    expect(typeof features.allowed_models[0].id).toBe("number");
    expect(patch).toMatchObject({
      username: "alice",
      can_manage_system: true,
      invite_quota_remaining: 5,
    });
  });
});
