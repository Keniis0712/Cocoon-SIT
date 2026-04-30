import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  t: vi.fn(),
  toastError: vi.fn(),
  createCocoonApiClient: vi.fn(),
}));

vi.mock("@/i18n", () => ({
  default: {
    t: mocks.t,
  },
}));

vi.mock("sonner", () => ({
  toast: {
    error: mocks.toastError,
  },
}));

vi.mock("@cocoon-sit/ts-sdk", () => ({
  ApiError: class MockApiError extends Error {
    status: number;
    data: unknown;

    constructor(status: number, data: unknown) {
      super(`Request failed with status ${status}`);
      this.status = status;
      this.data = data;
    }
  },
  createCocoonApiClient: mocks.createCocoonApiClient,
}));

import {
  apiJson,
  getApiBaseUrl,
  getErrorMessage,
  localizeApiMessage,
  showErrorToast,
} from "@/api/client";
import { ApiError } from "@cocoon-sit/ts-sdk";
import { useUserStore } from "@/store/useUserStore";

function resetUserStore() {
  useUserStore.setState({
    userInfo: {
      access_token: "token-1",
      refresh_token: "refresh-1",
      token_type: "bearer",
      expires_in_seconds: 3600,
      uid: "u-1",
      username: "alice",
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
      permissions: {},
      invite_quota_remaining: null,
      invite_quota_unlimited: true,
    },
    isLoggedIn: true,
    login: useUserStore.getState().login,
    logout: useUserStore.getState().logout,
    updateInfo: useUserStore.getState().updateInfo,
    getToken: useUserStore.getState().getToken,
  });
}

describe("api client helpers", () => {
  beforeEach(() => {
    mocks.t.mockReset();
    mocks.toastError.mockReset();
    mocks.createCocoonApiClient.mockReset();
    mocks.t.mockImplementation((key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
    );
    resetUserStore();
    vi.restoreAllMocks();
  });

  it("localizes exact and pattern-based api messages", () => {
    expect(localizeApiMessage("Invalid credentials")).toBe("common:apiErrors.authInvalidCredentials");
    expect(localizeApiMessage("Missing permission: users:write")).toBe(
      'common:apiErrors.missingPermission:{"permission":"users:write"}',
    );
    expect(localizeApiMessage("Custom backend message")).toBe("Custom backend message");
  });

  it("unwraps ApiError envelopes into localized messages", () => {
    const error = new ApiError(400, {
      code: "AUTH_INVALID_CREDENTIALS",
      msg: "Invalid credentials",
    });

    expect(getErrorMessage(error)).toBe("common:apiErrors.authInvalidCredentials");
    expect(getErrorMessage(new Error("Invite expired"))).toBe("common:apiErrors.inviteExpired");
  });

  it("uses the browser origin when no explicit api base url is configured", () => {
    expect(getApiBaseUrl()).toBe(window.location.origin);
  });

  it("sends auth headers and unwraps standard api envelopes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        status: 200,
        ok: true,
        text: vi.fn().mockResolvedValue(
          JSON.stringify({
            code: "OK",
            msg: "ok",
            data: { id: 1, name: "alice" },
          }),
        ),
      }),
    );

    const result = await apiJson<{ id: number; name: string }>("/users/me", {
      method: "PATCH",
      body: JSON.stringify({ timezone: "UTC" }),
    });

    expect(fetch).toHaveBeenCalledWith(
      `${window.location.origin}/api/v1/users/me`,
      expect.objectContaining({
        method: "PATCH",
        headers: expect.any(Headers),
      }),
    );

    const headers = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer token-1");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(result).toEqual({ id: 1, name: "alice" });
  });

  it("reports localized toast errors with fallback handling", () => {
    showErrorToast(new Error("Invalid token"), "fallback");
    showErrorToast(new Error("Request failed with status 500"), "fallback");

    expect(mocks.toastError).toHaveBeenNthCalledWith(1, "common:apiErrors.authInvalidToken");
    expect(mocks.toastError).toHaveBeenNthCalledWith(2, "fallback");
  });
});
