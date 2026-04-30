import { beforeEach, describe, expect, it } from "vitest";

import { useUserStore } from "@/store/useUserStore";
import type { SessionUser } from "@/api/user";

function sessionUser(overrides: Partial<SessionUser> = {}): SessionUser {
  return {
    access_token: "token-1",
    refresh_token: "refresh-1",
    token_type: "bearer",
    expires_in_seconds: 3600,
    uid: "1",
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
    permissions: { "users:read": true },
    invite_quota_remaining: null,
    invite_quota_unlimited: true,
    ...overrides,
  };
}

describe("useUserStore", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useUserStore.setState({
      userInfo: null,
      isLoggedIn: false,
      login: useUserStore.getState().login,
      logout: useUserStore.getState().logout,
      updateInfo: useUserStore.getState().updateInfo,
      getToken: useUserStore.getState().getToken,
    });
  });

  it("logs users in and exposes the stored token", () => {
    const store = useUserStore.getState();
    store.login(sessionUser());

    expect(useUserStore.getState().isLoggedIn).toBe(true);
    expect(useUserStore.getState().userInfo?.username).toBe("alice");
    expect(useUserStore.getState().getToken()).toBe("token-1");
  });

  it("merges profile updates and clears state on logout", () => {
    const store = useUserStore.getState();
    store.login(sessionUser());
    store.updateInfo({
      username: "bob",
      timezone: "Asia/Shanghai",
      permissions: { "users:read": true, "roles:write": true },
    });

    expect(useUserStore.getState().userInfo).toMatchObject({
      username: "bob",
      timezone: "Asia/Shanghai",
      permissions: { "users:read": true, "roles:write": true },
    });

    store.logout();

    expect(useUserStore.getState().isLoggedIn).toBe(false);
    expect(useUserStore.getState().userInfo).toBeNull();
    expect(useUserStore.getState().getToken()).toBeNull();
  });
});
