import { apiCall, apiJson } from "./client";
import { rememberLegacyId, rememberLegacyStringId, resolveActualId } from "./id-map";
import type {
  InviteCodeCreatePayload,
  InviteCodeRead,
  InviteQuotaAccountRead,
  InviteQuotaGrantCreatePayload,
  InviteQuotaGrantRead,
  InviteSummary,
  InviteQuotaUpdatePayload,
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

type InviteCodeResponse = {
  id: string;
  code: string;
  created_by_user_id: string | null;
  created_for_user_id: string | null;
  registration_group_id: string | null;
  source_type: string;
  source_id: string | null;
  quota_total: number;
  quota_used: number;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
  updated_at: string;
};

type InviteGrantResponse = {
  id: string;
  granted_by_user_id: string | null;
  target_type: string;
  target_id: string;
  quota: number;
  is_unlimited: boolean;
  note: string | null;
  created_at: string;
  revoked_at: string | null;
};

type InviteQuotaAccountResponse = {
  target_type: string;
  target_id: string;
  invite_quota_remaining: number;
  invite_quota_unlimited: boolean;
  updated_at: string;
};

function mapInvite(item: InviteCodeResponse): InviteCodeRead {
  return {
    code: item.code,
    created_by_uid: item.created_by_user_id ? rememberLegacyStringId("user", item.created_by_user_id) : "",
    parent_uid: item.created_for_user_id
      ? rememberLegacyStringId("user", item.created_for_user_id)
      : item.created_by_user_id
        ? rememberLegacyStringId("user", item.created_by_user_id)
        : "",
    registration_group_id: item.registration_group_id ? rememberLegacyStringId("group", item.registration_group_id) : null,
    source_type: item.source_type as InviteCodeRead["source_type"],
    source_id:
      item.source_type === "USER" && item.source_id
        ? rememberLegacyStringId("user", item.source_id)
        : item.source_type === "GROUP" && item.source_id
          ? rememberLegacyStringId("group", item.source_id)
          : item.source_id,
    expires_at: item.expires_at,
    consumed_at: item.quota_used >= item.quota_total ? item.updated_at : null,
    consumed_by_uid: null,
    revoked_at: item.revoked_at,
    created_at: item.created_at,
  };
}

function mapGrant(item: InviteGrantResponse): InviteQuotaGrantRead {
  return {
    id: rememberLegacyId("invite", item.id),
    granter_uid: item.granted_by_user_id ? rememberLegacyStringId("user", item.granted_by_user_id) : "",
    target_type: item.target_type as InviteQuotaGrantRead["target_type"],
    target_id:
      item.target_type === "USER"
        ? rememberLegacyStringId("user", item.target_id)
        : item.target_type === "GROUP"
          ? rememberLegacyStringId("group", item.target_id)
          : item.target_id,
    amount: item.quota,
    is_unlimited: item.is_unlimited,
    note: item.note,
    created_at: item.created_at,
    revoked_at: item.revoked_at,
  };
}

function mapQuotaAccount(item: InviteQuotaAccountResponse): InviteQuotaAccountRead {
  return {
    target_type: item.target_type as InviteQuotaAccountRead["target_type"],
    target_id:
      item.target_type === "USER"
        ? rememberLegacyStringId("user", item.target_id)
        : item.target_type === "GROUP"
          ? rememberLegacyStringId("group", item.target_id)
          : item.target_id,
    invite_quota_remaining: item.invite_quota_remaining,
    invite_quota_unlimited: item.invite_quota_unlimited,
    updated_at: item.updated_at,
  };
}

export function listInviteCodes(
  page: number,
  page_size: number,
  params?: { created_by_uid?: string },
): Promise<PageResp<InviteCodeRead>> {
  return apiCall(async () => {
    const items = (await apiJson<InviteCodeResponse[]>("/invites"))
      .map(mapInvite)
      .filter((item) => !params?.created_by_uid || item.created_by_uid === params.created_by_uid);
    return makePage(items, page, page_size);
  });
}

export function createInviteCode(data: InviteCodeCreatePayload): Promise<InviteCodeRead> {
  return apiCall(async () => {
    const sourceType = data.source_type;
    const sourceId =
      sourceType === "USER" && data.source_id
        ? resolveActualId("user", data.source_id)
        : sourceType === "GROUP" && data.source_id
          ? resolveActualId("group", data.source_id)
          : data.source_id ?? null;
    const created = await apiJson<InviteCodeResponse>("/invites", {
      method: "POST",
      body: JSON.stringify({
        prefix: data.prefix?.trim() || "invite",
        quota_total: 1,
        expires_at: data.permanent ? null : data.expires_at ?? null,
        created_for_user_id: data.created_for_uid ? resolveActualId("user", data.created_for_uid) : null,
        registration_group_id: resolveActualId("group", data.registration_group_id),
        source_type: sourceType,
        source_id: sourceId,
      }),
    });
    return mapInvite(created);
  });
}

export function deleteInviteCode(code: string) {
  return apiCall(async (client) => {
    await client.revokeInvite(code);
  });
}

export function listInviteGrants(page: number, page_size: number): Promise<PageResp<InviteQuotaGrantRead>> {
  return apiCall(async () => {
    const items = (await apiJson<InviteGrantResponse[]>("/invites/grants")).map(mapGrant);
    return makePage(items, page, page_size);
  });
}

export function createInviteGrant(data: InviteQuotaGrantCreatePayload): Promise<InviteQuotaGrantRead> {
  return apiCall(async () => {
    const created = await apiJson<InviteGrantResponse>("/invites/grants", {
      method: "POST",
      body: JSON.stringify({
        target_type: data.target_type,
        target_id:
          data.target_type === "USER"
            ? resolveActualId("user", data.target_id)
            : resolveActualId("group", data.target_id),
        amount: data.amount,
        is_unlimited: data.is_unlimited,
        note: data.note ?? null,
      }),
    });
    return mapGrant(created);
  });
}

export function revokeInviteGrant(grantId: number) {
  return apiCall(async () => {
    const created = await apiJson<InviteGrantResponse>(`/invites/grants/${resolveActualId("invite", grantId)}`, {
      method: "DELETE",
    });
    return mapGrant(created);
  });
}

export function listInviteQuotaAccounts(): Promise<InviteQuotaAccountRead[]> {
  return apiCall(async () => {
    const items = await apiJson<InviteQuotaAccountResponse[]>("/invites/quotas");
    return items.map(mapQuotaAccount);
  });
}

export function updateInviteQuota(
  targetType: "USER" | "GROUP",
  targetId: string,
  data: InviteQuotaUpdatePayload,
): Promise<InviteSummary> {
  return apiCall(async () => {
    const summary = await apiJson<InviteQuotaAccountResponse>(
      `/invites/quotas/${targetType}/${targetType === "USER" ? resolveActualId("user", targetId) : resolveActualId("group", targetId)}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          invite_quota_remaining: data.invite_quota_remaining,
          invite_quota_unlimited: data.invite_quota_unlimited,
        }),
      },
    );
    return {
      target_type: summary.target_type as InviteSummary["target_type"],
      target_id:
        summary.target_type === "USER"
          ? rememberLegacyStringId("user", summary.target_id)
          : summary.target_type === "GROUP"
            ? rememberLegacyStringId("group", summary.target_id)
            : summary.target_id,
      invite_quota_remaining: summary.invite_quota_remaining,
      invite_quota_unlimited: summary.invite_quota_unlimited,
    };
  });
}

export function getMyInviteSummary(): Promise<InviteSummary> {
  return apiCall(async (client) => {
    const summary = await client.getMyInviteSummary();
    return {
      target_type: summary.target_type as InviteSummary["target_type"],
      target_id: rememberLegacyStringId("user", summary.target_id),
      invite_quota_remaining: summary.invite_quota_remaining,
      invite_quota_unlimited: summary.invite_quota_unlimited,
    };
  });
}

export function getGroupInviteSummary(gid: string): Promise<InviteSummary> {
  return apiCall(async (client) => {
    const summary = await client.getGroupInviteSummary(resolveActualId("group", gid));
    return {
      target_type: summary.target_type as InviteSummary["target_type"],
      target_id: rememberLegacyStringId("group", summary.target_id),
      invite_quota_remaining: summary.invite_quota_remaining,
      invite_quota_unlimited: summary.invite_quota_unlimited,
    };
  });
}
