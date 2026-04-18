import { apiCall, unsupportedFeature } from "./client";
import {
  rememberLegacyStringId,
  resolveActualId,
} from "./id-map";
import type {
  InviteCodeCreatePayload,
  InviteCodeRead,
  InviteQuotaGrantCreatePayload,
  InviteQuotaGrantRead,
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
        parent_uid: item.created_by_user_id ? rememberLegacyStringId("user", item.created_by_user_id) : "",
        source_type: "ADMIN_OVERRIDE" as const,
        source_id: null,
        expires_at: item.expires_at,
        consumed_at: item.quota_used >= item.quota_total ? item.created_at : null,
        consumed_by_uid: null,
        revoked_at: null,
        created_at: item.created_at,
      }))
      .filter((item) => !params?.created_by_uid || item.created_by_uid === params.created_by_uid);
    return makePage(items, page, page_size);
  });
}

export function createInviteCode(data: InviteCodeCreatePayload): Promise<InviteCodeRead> {
  return apiCall(async (client) => {
    const created = await client.createInvite({
      code: data.prefix?.trim() || `invite-${Date.now()}`,
      quota_total: 1,
      expires_at: data.permanent ? null : data.expires_at ?? null,
    });
    const sourceId =
      data.source_type === "USER" && data.source_id
        ? rememberLegacyStringId("user", resolveActualId("user", data.source_id))
        : data.source_type === "GROUP" && data.source_id
          ? rememberLegacyStringId("group", resolveActualId("group", data.source_id))
          : data.source_id ?? null;
    return {
      code: created.code,
      created_by_uid: created.created_by_user_id ? rememberLegacyStringId("user", created.created_by_user_id) : "",
      parent_uid: created.created_by_user_id ? rememberLegacyStringId("user", created.created_by_user_id) : "",
      source_type: data.source_type,
      source_id: sourceId,
      expires_at: created.expires_at,
      consumed_at: created.quota_used >= created.quota_total ? created.created_at : null,
      consumed_by_uid: null,
      revoked_at: null,
      created_at: created.created_at,
    };
  });
}

export function deleteInviteCode(_code: string) {
  return unsupportedFeature("当前后端暂不支持撤销邀请码");
}

export function listInviteGrants(page: number, page_size: number): Promise<PageResp<InviteQuotaGrantRead>> {
  return Promise.resolve(
    makePage<InviteQuotaGrantRead>([], page, page_size),
  );
}

export function createInviteGrant(_data: InviteQuotaGrantCreatePayload): Promise<InviteQuotaGrantRead> {
  return unsupportedFeature("当前后端暂不支持在控制台里直接发放邀请码额度");
}
