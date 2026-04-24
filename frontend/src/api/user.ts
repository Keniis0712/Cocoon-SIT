import type { Schemas } from "@cocoon-sit/ts-sdk";

import { apiCall, apiJson, createAnonymousClient, createTokenClient } from "./client";
import { rememberLegacyId, rememberLegacyStringId } from "./id-map";
import type { PublicFeaturesRead } from "./types/providers";

type PermissionMap = Record<string, boolean>;

export interface SessionUser {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in_seconds: number;
  uid: string;
  username: string;
  parent_uid: string | null;
  user_path: string | null;
  role: string;
  role_level: number;
  can_audit: boolean;
  can_manage_system: boolean;
  can_manage_users: boolean;
  can_manage_prompts: boolean;
  can_manage_providers: boolean;
  permissions: PermissionMap;
  invite_quota_remaining: number | null;
  invite_quota_unlimited: boolean | null;
}

export interface MeResponse {
  uid: string;
  username: string;
  email: string | null;
  parent_uid: string | null;
  user_path: string | null;
  role: string;
  role_level: number;
  can_audit: boolean;
  can_manage_system: boolean;
  can_manage_users: boolean;
  can_manage_prompts: boolean;
  can_manage_providers: boolean;
  permissions: PermissionMap;
  invite_quota_remaining: number | null;
  invite_quota_unlimited: boolean | null;
  created_at: string;
}

export interface ImBindTokenResponse {
  token: string;
  expires_at: string;
  expires_in_seconds: number;
}

export type RegisterPayload = {
  username: string;
  password: string;
  email?: string | null;
  invite_code: string;
};

function roleLevel(roleName: string) {
  if (roleName === "admin") return 0;
  if (roleName === "operator") return 1;
  return 2;
}

function rolePermissions(role: Schemas["RoleOut"] | null): PermissionMap {
  return role?.permissions_json || {};
}

function buildMeResponse(
  user: Schemas["UserOut"],
  role: Schemas["RoleOut"] | null,
): MeResponse {
  const permissions = rolePermissions(role);
  return {
    uid: rememberLegacyStringId("user", user.id),
    username: user.username,
    email: user.email ?? null,
    parent_uid: null,
    user_path: null,
    role: role?.name || "user",
    role_level: roleLevel(role?.name || "user"),
    can_audit: Boolean(permissions["audits:read"]),
    can_manage_system: Boolean(
      permissions["settings:read"] ||
        permissions["settings:write"] ||
        permissions["roles:write"] ||
        permissions["prompt_templates:write"] ||
        permissions["artifacts:cleanup"],
    ),
    can_manage_users: Boolean(permissions["users:read"] || permissions["users:write"]),
    can_manage_prompts: Boolean(
      permissions["prompt_templates:read"] || permissions["prompt_templates:write"],
    ),
    can_manage_providers: Boolean(permissions["providers:read"] || permissions["providers:write"]),
    permissions,
    invite_quota_remaining: null,
    invite_quota_unlimited: null,
    created_at: user.created_at,
  };
}

async function fetchProfile(accessToken: string) {
  const client = createTokenClient(accessToken);
  const user = await client.me();
  let role: Schemas["RoleOut"] | null = null;

  if (user.role_id) {
    try {
      const roles = await client.listRoles();
      role = roles.find((item) => item.id === user.role_id) ?? null;
    } catch {
      role = null;
    }
  }

  return buildMeResponse(user, role);
}

export async function login(username: string, password: string): Promise<SessionUser> {
  const tokenPair = await createAnonymousClient().login({ username, password });
  const profile = await fetchProfile(tokenPair.access_token);

  return {
    access_token: tokenPair.access_token,
    refresh_token: tokenPair.refresh_token,
    token_type: "bearer",
    expires_in_seconds: 0,
    ...profile,
  };
}

export async function register(data: RegisterPayload): Promise<SessionUser> {
  const tokenPair = await createAnonymousClient().register(data);
  const profile = await fetchProfile(tokenPair.access_token);

  return {
    access_token: tokenPair.access_token,
    refresh_token: tokenPair.refresh_token,
    token_type: "bearer",
    expires_in_seconds: 0,
    ...profile,
  };
}

export async function me(): Promise<MeResponse> {
  return apiCall(async (client) => {
    const user = await client.me();
    let role: Schemas["RoleOut"] | null = null;
    if (user.role_id) {
      try {
        const roles = await client.listRoles();
        role = roles.find((item) => item.id === user.role_id) ?? null;
      } catch {
        role = null;
      }
    }
    return buildMeResponse(user, role);
  });
}

export async function createImBindToken(): Promise<ImBindTokenResponse> {
  return apiJson<ImBindTokenResponse>("/auth/me/im-bind-token", {
    method: "POST",
  });
}

export async function logout(refresh_token: string): Promise<undefined> {
  await apiCall((client) => client.logout({ refresh_token }));
  return undefined;
}

export async function changePassword(
  _old_password: string,
  _new_password: string,
): Promise<undefined> {
  throw new Error("Password change is not exposed by the current backend");
}

export async function changeUsername(_username: string): Promise<MeResponse> {
  throw new Error("Username change is not exposed by the current backend");
}

export async function getPublicFeatures(): Promise<PublicFeaturesRead> {
  const features = await createAnonymousClient().getPublicFeatures();
  return {
    allow_registration: features.allow_registration,
    max_chat_turns: features.max_chat_turns,
    allowed_models: features.allowed_models.map((item) => ({
      id: rememberLegacyId("model", item.id),
      provider_id: rememberLegacyId("provider", item.provider_id),
      provider_name: "",
      model_name: item.model_name,
    })),
    rollback_retention_days: features.rollback_retention_days,
    rollback_cleanup_interval_hours: features.rollback_cleanup_interval_hours,
  };
}
