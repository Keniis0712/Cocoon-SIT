import { apiCall } from "./client";
import { rememberLegacyId, rememberLegacyStringId, resolveActualId } from "./id-map";
import type {
  InviteCodeCreatePayload,
  InviteCodeRead,
  InviteQuotaGrantCreatePayload,
  InviteQuotaGrantRead,
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

export function listInviteCodes(
  page: number,
  page_size: number,
  params?: { created_by_uid?: string },
): Promise<PageResp<InviteCodeRead>> {
  return apiCall(async (client) => {
    const items = (await client.listInvites())
      .map((item) => ({
        code: item.code,
        created_by_uid: item.created_by_user_id ? rememberLegacyStringId("user", item.created_by_user_id) : "",
        parent_uid: item.created_for_user_id
          ? rememberLegacyStringId("user", item.created_for_user_id)
          : item.created_by_user_id
            ? rememberLegacyStringId("user", item.created_by_user_id)
            : "",
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
      }))
      .filter((item) => !params?.created_by_uid || item.created_by_uid === params.created_by_uid);
    return makePage(items, page, page_size);
  });
}

export function createInviteCode(data: InviteCodeCreatePayload): Promise<InviteCodeRead> {
  return apiCall(async (client) => {
    const sourceType = data.source_type;
    const sourceId =
      sourceType === "USER" && data.source_id
        ? resolveActualId("user", data.source_id)
        : sourceType === "GROUP" && data.source_id
          ? resolveActualId("group", data.source_id)
          : data.source_id ?? null;
    const created = await client.createInvite({
      prefix: data.prefix?.trim() || "invite",
      quota_total: 1,
      expires_at: data.permanent ? null : data.expires_at ?? null,
      created_for_user_id: data.created_for_uid ? resolveActualId("user", data.created_for_uid) : null,
      source_type: sourceType,
      source_id: sourceId,
    });
    return {
      code: created.code,
      created_by_uid: created.created_by_user_id ? rememberLegacyStringId("user", created.created_by_user_id) : "",
      parent_uid: created.created_for_user_id
        ? rememberLegacyStringId("user", created.created_for_user_id)
        : created.created_by_user_id
          ? rememberLegacyStringId("user", created.created_by_user_id)
          : "",
      source_type: created.source_type as InviteCodeRead["source_type"],
      source_id:
        created.source_type === "USER" && created.source_id
          ? rememberLegacyStringId("user", created.source_id)
          : created.source_type === "GROUP" && created.source_id
            ? rememberLegacyStringId("group", created.source_id)
            : created.source_id,
      expires_at: created.expires_at,
      consumed_at: created.quota_used >= created.quota_total ? created.updated_at : null,
      consumed_by_uid: null,
      revoked_at: created.revoked_at,
      created_at: created.created_at,
    };
  });
}

export function deleteInviteCode(code: string) {
  return apiCall(async (client) => {
    await client.revokeInvite(code);
  });
}

export function listInviteGrants(page: number, page_size: number): Promise<PageResp<InviteQuotaGrantRead>> {
  return apiCall(async (client) => {
    const items = (await client.listInviteGrants()).map((item) => ({
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
    }));
    return makePage(items, page, page_size);
  });
}

export function createInviteGrant(data: InviteQuotaGrantCreatePayload): Promise<InviteQuotaGrantRead> {
  return apiCall(async (client) => {
    const created = await client.createInviteGrant({
      target_type: data.target_type,
      target_id:
        data.target_type === "USER"
          ? resolveActualId("user", data.target_id)
          : resolveActualId("group", data.target_id),
      amount: data.amount,
      is_unlimited: data.is_unlimited,
      note: data.note ?? null,
    });
    return {
      id: rememberLegacyId("invite", created.id),
      granter_uid: created.granted_by_user_id ? rememberLegacyStringId("user", created.granted_by_user_id) : "",
      target_type: created.target_type as InviteQuotaGrantRead["target_type"],
      target_id:
        created.target_type === "USER"
          ? rememberLegacyStringId("user", created.target_id)
          : created.target_type === "GROUP"
            ? rememberLegacyStringId("group", created.target_id)
            : created.target_id,
      amount: created.quota,
      is_unlimited: created.is_unlimited,
      note: created.note,
      created_at: created.created_at,
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
