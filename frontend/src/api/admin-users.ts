import type { Schemas } from "@cocoon-sit/ts-sdk";

import { apiCall } from "./client";
import { rememberLegacyStringId, resolveActualId } from "./id-map";
import type {
  AdminUserCreatePayload,
  AdminUserRead,
  AdminUserUpdatePayload,
  InviteSummary,
  PageResp,
} from "./types";

function makePage<T>(items: T[], page: number, pageSize: number): PageResp<T> {
  const total = items.length;
  const total_pages = Math.max(1, Math.ceil(total / pageSize));
  const start = Math.max(0, (page - 1) * pageSize);
  return {
    items: items.slice(start, start + pageSize),
    total,
    page,
    page_size: pageSize,
    total_pages,
  };
}

function roleLevel(roleName: string) {
  if (roleName === "admin") return 0;
  if (roleName === "operator") return 1;
  return 2;
}

function rolePermissions(role: Schemas["RoleOut"] | null) {
  return role?.permissions_json || {};
}

function mapUser(user: Schemas["UserOut"], role: Schemas["RoleOut"] | null): AdminUserRead {
  const roleName = role?.name || "user";
  const permissions = rolePermissions(role);
  return {
    uid: rememberLegacyStringId("user", user.id),
    username: user.username,
    email: user.email ?? null,
    parent_uid: null,
    user_path: null,
    invite_code: null,
    role: roleName,
    role_level: roleLevel(roleName),
    can_audit: Boolean(permissions["audits:read"]),
    is_active: user.is_active,
    token_version: null,
    quota_tokens: null,
    invite_quota_remaining: null,
    invite_quota_unlimited: null,
    last_login_at: null,
    created_at: user.created_at,
    updated_at: user.created_at,
  };
}

async function loadRoles() {
  return apiCall((client) => client.listRoles());
}

export function listAdminUsers(
  page: number,
  page_size: number,
  params?: { q?: string; role?: string },
): Promise<PageResp<AdminUserRead>> {
  return apiCall(async (client) => {
    const [users, roles] = await Promise.all([client.listUsers(), loadRoles()]);
    const roleMap = new Map(roles.map((item) => [item.id, item] as const));
    const items = users
      .map((user) => mapUser(user, user.role_id ? roleMap.get(user.role_id) ?? null : null))
      .filter((user) => {
        if (params?.q && !user.username.includes(params.q) && !(user.email || "").includes(params.q)) {
          return false;
        }
        if (params?.role && user.role !== params.role) {
          return false;
        }
        return true;
      });
    return makePage(items, page, page_size);
  });
}

export function createAdminUser(data: AdminUserCreatePayload): Promise<AdminUserRead> {
  return apiCall(async (client) => {
    const roles = await client.listRoles();
    const role = roles.find((item) => item.name === data.role) ?? null;
    const user = await client.createUser({
      username: data.username,
      email: data.email ?? null,
      password: data.password,
      role_id: role?.id ?? null,
      is_active: true,
    });
    return mapUser(user, role);
  });
}

export function updateAdminUser(userUid: string, data: AdminUserUpdatePayload): Promise<AdminUserRead> {
  return apiCall(async (client) => {
    const roles = await client.listRoles();
    const role = data.role ? roles.find((item) => item.name === data.role) ?? null : null;
    const user = await client.updateUser(resolveActualId("user", userUid), {
      email: data.email ?? null,
      role_id: data.role ? role?.id ?? null : undefined,
      is_active: data.is_active ?? undefined,
      password: data.password ?? undefined,
    });
    const resolvedRole = user.role_id ? roles.find((item) => item.id === user.role_id) ?? role : role;
    return mapUser(user, resolvedRole ?? null);
  });
}

export function getUserInviteSummary(userUid: string): Promise<InviteSummary> {
  return apiCall(async (client) => {
    const summary = await client.getMyInviteSummary();
    if (summary.target_id === resolveActualId("user", userUid)) {
      return {
        target_type: summary.target_type,
        target_id: userUid,
        invite_quota_remaining: summary.invite_quota_remaining,
        invite_quota_unlimited: summary.invite_quota_unlimited,
      };
    }
    return {
      target_type: "USER",
      target_id: userUid,
      invite_quota_remaining: 0,
      invite_quota_unlimited: false,
    };
  });
}
