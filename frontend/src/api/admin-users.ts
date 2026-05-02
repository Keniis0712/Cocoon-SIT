import { apiCall, apiJson } from "./client";
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

type ManagedUserResponse = {
  id: string;
  username: string;
  email: string | null;
  role_id: string | null;
  role_name: string | null;
  primary_group_id: string | null;
  primary_group_path?: string | null;
  permissions_json: Record<string, boolean>;
  effective_permissions: Record<string, boolean>;
  timezone: string;
  is_active: boolean;
  is_bootstrap_admin?: boolean;
  has_management_console?: boolean;
  created_at: string;
};

function roleLevel(roleName: string | null) {
  if (roleName === "admin") return 0;
  if (roleName === "operator") return 1;
  return 2;
}

function mapUser(user: ManagedUserResponse): AdminUserRead {
  const roleName = user.role_name || null;
  const permissions = user.effective_permissions || {};
  return {
    uid: rememberLegacyStringId("user", user.id),
    username: user.username,
    email: user.email ?? null,
    parent_uid: null,
    user_path: null,
    primary_group_id: user.primary_group_id ? rememberLegacyStringId("group", user.primary_group_id) : null,
    primary_group_path: user.primary_group_path ?? null,
    invite_code: null,
    role: roleName,
    role_level: roleLevel(roleName),
    can_audit: Boolean(permissions["audits:read"]),
    is_active: user.is_active,
    is_bootstrap_admin: Boolean(user.is_bootstrap_admin),
    has_management_console: Boolean(user.has_management_console),
    timezone: user.timezone || "UTC",
    permissions_json: user.permissions_json || {},
    effective_permissions: permissions,
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

async function listManagedUsers() {
  return apiJson<ManagedUserResponse[]>("/users");
}

async function listScopedUsers(scope: "all" | "manageable") {
  return apiJson<ManagedUserResponse[]>(`/users?scope=${scope}`);
}

export function listAdminUsers(
  page: number,
  page_size: number,
  params?: { q?: string; role?: string; scope?: "all" | "manageable" },
): Promise<PageResp<AdminUserRead>> {
  return apiCall(async () => {
    const users = params?.scope ? await listScopedUsers(params.scope) : await listManagedUsers();
    const items = users
      .map(mapUser)
      .filter((user) => {
        if (params?.q && !user.username.includes(params.q) && !(user.email || "").includes(params.q)) {
          return false;
        }
        if (params?.role && (user.role || "") !== params.role) {
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
    const role = data.role ? roles.find((item) => item.name === data.role) ?? null : null;
    const user = await apiJson<ManagedUserResponse>("/users", {
      method: "POST",
      body: JSON.stringify({
        username: data.username,
        email: data.email ?? null,
        password: data.password,
        role_id: role?.id ?? null,
        primary_group_id: data.primary_group_id ? resolveActualId("group", data.primary_group_id) : undefined,
        timezone: data.timezone ?? "UTC",
        permissions_json: data.permissions_json || {},
        is_active: true,
      }),
    });
    return mapUser(user);
  });
}

export function updateAdminUser(userUid: string, data: AdminUserUpdatePayload): Promise<AdminUserRead> {
  return apiCall(async (client) => {
    const roles = await client.listRoles();
    const role = data.role ? roles.find((item) => item.name === data.role) ?? null : null;
    const user = await apiJson<ManagedUserResponse>(`/users/${resolveActualId("user", userUid)}`, {
      method: "PATCH",
      body: JSON.stringify({
        email: data.email ?? null,
        role_id: data.role !== undefined ? role?.id ?? null : undefined,
        primary_group_id:
          data.primary_group_id === undefined
            ? undefined
            : data.primary_group_id
              ? resolveActualId("group", data.primary_group_id)
              : null,
        timezone: data.timezone ?? undefined,
        permissions_json: data.permissions_json ?? undefined,
        is_active: data.is_active ?? undefined,
        password: data.password ?? undefined,
      }),
    });
    return mapUser(user);
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
