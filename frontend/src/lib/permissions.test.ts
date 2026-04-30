import { describe, expect, it } from "vitest";

import { hasAnyPermission, hasPermission } from "@/lib/permissions";
import type { SessionUser } from "@/api/user";

function sessionUser(permissions: Record<string, boolean>): SessionUser {
  return {
    access_token: "token",
    refresh_token: "refresh",
    token_type: "bearer",
    expires_in_seconds: 3600,
    uid: "1",
    username: "tester",
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
    permissions,
    invite_quota_remaining: null,
    invite_quota_unlimited: true,
  };
}

describe("permissions helpers", () => {
  it("returns false when the user or permission is missing", () => {
    expect(hasPermission(null, "users:read")).toBe(false);
    expect(hasPermission(sessionUser({}), "users:read")).toBe(false);
  });

  it("matches individual and grouped permissions", () => {
    const user = sessionUser({
      "users:read": false,
      "providers:write": true,
      "settings:read": true,
    });

    expect(hasPermission(user, "providers:write")).toBe(true);
    expect(hasAnyPermission(user, ["users:read", "settings:read"])).toBe(true);
    expect(hasAnyPermission(user, ["users:read", "roles:write"])).toBe(false);
  });
});
