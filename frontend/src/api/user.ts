import { ApiError } from "@cocoon-sit/ts-sdk";

import { apiCall, apiJson, createAnonymousClient, getApiBaseUrl, getErrorMessage } from "./client";
import { rememberLegacyId, rememberLegacyStringId } from "./id-map";
import type { PublicFeaturesRead } from "./types/providers";

type PermissionMap = Record<string, boolean>;

type AuthMeProfileResponse = {
  id: string;
  username: string;
  email: string | null;
  role_id: string | null;
  role_name: string | null;
  is_active: boolean;
  created_at: string;
  permissions: PermissionMap;
};

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

function buildMeResponse(profile: AuthMeProfileResponse): MeResponse {
  const permissions = profile.permissions || {};
  const roleName = profile.role_name || (Object.keys(permissions).length > 0 ? "direct" : "user");
  return {
    uid: rememberLegacyStringId("user", profile.id),
    username: profile.username,
    email: profile.email ?? null,
    parent_uid: null,
    user_path: null,
    role: roleName,
    role_level: roleLevel(roleName),
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
    created_at: profile.created_at,
  };
}

export function buildSessionPatch(profile: MeResponse): Partial<SessionUser> {
  return {
    uid: profile.uid,
    username: profile.username,
    parent_uid: profile.parent_uid,
    user_path: profile.user_path,
    role: profile.role,
    role_level: profile.role_level,
    can_audit: profile.can_audit,
    can_manage_system: profile.can_manage_system,
    can_manage_users: profile.can_manage_users,
    can_manage_prompts: profile.can_manage_prompts,
    can_manage_providers: profile.can_manage_providers,
    permissions: profile.permissions,
    invite_quota_remaining: profile.invite_quota_remaining,
    invite_quota_unlimited: profile.invite_quota_unlimited,
  };
}

async function fetchProfileWithAccessToken(accessToken: string): Promise<AuthMeProfileResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/me`, {
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
  });

  const rawText = await response.text();
  let payload: unknown = null;
  if (rawText) {
    try {
      payload = JSON.parse(rawText);
    } catch {
      payload = rawText;
    }
  }

  if (!response.ok) {
    throw new Error(getErrorMessage(new ApiError(response.status, payload)));
  }

  return payload as AuthMeProfileResponse;
}

export async function login(username: string, password: string): Promise<SessionUser> {
  const tokenPair = await createAnonymousClient().login({ username, password });
  const profile = await fetchProfileWithAccessToken(tokenPair.access_token);
  const session = buildMeResponse(profile);

  return {
    access_token: tokenPair.access_token,
    refresh_token: tokenPair.refresh_token,
    token_type: "bearer",
    expires_in_seconds: 0,
    ...session,
  };
}

export async function register(data: RegisterPayload): Promise<SessionUser> {
  const tokenPair = await createAnonymousClient().register(data);
  const profile = await fetchProfileWithAccessToken(tokenPair.access_token);
  const session = buildMeResponse(profile);

  return {
    access_token: tokenPair.access_token,
    refresh_token: tokenPair.refresh_token,
    token_type: "bearer",
    expires_in_seconds: 0,
    ...session,
  };
}

export async function me(): Promise<MeResponse> {
  const profile = await apiJson<AuthMeProfileResponse>("/auth/me");
  return buildMeResponse(profile);
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
