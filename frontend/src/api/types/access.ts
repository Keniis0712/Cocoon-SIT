export interface AdminUserRead {
  uid: string;
  username: string;
  email: string | null;
  parent_uid: string | null;
  user_path: string | null;
  invite_code: string | null;
  role: string;
  role_level: number;
  can_audit: boolean;
  is_active: boolean;
  token_version: number | null;
  quota_tokens: number | null;
  invite_quota_remaining: number | null;
  invite_quota_unlimited: boolean | null;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminUserCreatePayload {
  username: string;
  password: string;
  email?: string | null;
  role: string;
  role_level: number;
  can_audit: boolean;
  parent_uid?: string | null;
  invite_quota_remaining?: number;
  invite_quota_unlimited?: boolean;
}

export interface AdminUserUpdatePayload {
  email?: string | null;
  role?: string | null;
  role_level?: number | null;
  can_audit?: boolean | null;
  is_active?: boolean | null;
  password?: string | null;
  invite_quota_remaining?: number | null;
  invite_quota_unlimited?: boolean | null;
}

export interface RoleRead {
  code: string;
  name: string;
  description: string | null;
  permissions_json: string;
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export interface GroupRead {
  gid: string;
  name: string;
  owner_uid: string;
  parent_group_id: string | null;
  group_path: string | null;
  invite_quota_remaining: number | null;
  invite_quota_unlimited: boolean | null;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface GroupCreatePayload {
  name: string;
  parent_group_id?: string | null;
  description?: string | null;
}

export interface GroupUpdatePayload {
  name?: string | null;
  parent_group_id?: string | null;
  description?: string | null;
  invite_quota_remaining?: number | null;
  invite_quota_unlimited?: boolean | null;
}

export interface GroupMemberRead {
  id: number;
  group_id: string;
  user_uid: string;
  created_at: string;
}

export interface InviteSummary {
  target_type: "USER" | "GROUP" | string;
  target_id: string;
  invite_quota_remaining: number;
  invite_quota_unlimited: boolean;
}

export interface InviteCodeRead {
  code: string;
  created_by_uid: string;
  parent_uid: string;
  source_type: "USER" | "GROUP" | "ADMIN_OVERRIDE" | string;
  source_id: string | null;
  expires_at: string | null;
  consumed_at: string | null;
  consumed_by_uid: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface InviteCodeCreatePayload {
  created_for_uid?: string | null;
  source_type: "USER" | "GROUP" | "ADMIN_OVERRIDE";
  source_id?: string | null;
  expires_at?: string | null;
  permanent?: boolean;
  prefix?: string | null;
}

export interface InviteQuotaGrantRead {
  id: number;
  granter_uid: string;
  target_type: "USER" | "GROUP" | string;
  target_id: string;
  amount: number;
  is_unlimited: boolean;
  note: string | null;
  created_at: string;
}

export interface InviteQuotaGrantCreatePayload {
  target_type: "USER" | "GROUP";
  target_id: string;
  amount: number;
  is_unlimited: boolean;
  note?: string | null;
}

