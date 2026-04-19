import { apiCall } from "./client";
import {
  rememberLegacyId,
  rememberLegacyStringId,
  resolveActualId,
} from "./id-map";
import type {
  GroupCreatePayload,
  GroupMemberRead,
  GroupRead,
  GroupUpdatePayload,
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

export function listGroups(page: number, page_size: number, params?: { q?: string }): Promise<PageResp<GroupRead>> {
  return apiCall(async (client) => {
    const items = (await client.listGroups())
      .map((item) => ({
        gid: rememberLegacyStringId("group", item.id),
        name: item.name,
        owner_uid: item.owner_user_id ? rememberLegacyStringId("user", item.owner_user_id) : "",
        parent_group_id: null,
        group_path: null,
        invite_quota_remaining: null,
        invite_quota_unlimited: null,
        description: null,
        created_at: item.created_at,
        updated_at: item.created_at,
      }))
      .filter((item) => !params?.q || item.name.includes(params.q));
    return makePage(items, page, page_size);
  });
}

export function createGroup(data: GroupCreatePayload): Promise<GroupRead> {
  return apiCall(async (client) => {
    const group = await client.createGroup({ name: data.name.trim() });
    return {
      gid: rememberLegacyStringId("group", group.id),
      name: group.name,
      owner_uid: group.owner_user_id ? rememberLegacyStringId("user", group.owner_user_id) : "",
      parent_group_id: null,
      group_path: null,
      invite_quota_remaining: null,
      invite_quota_unlimited: null,
      description: null,
      created_at: group.created_at,
      updated_at: group.created_at,
    };
  });
}

export function updateGroup(_gid: string, _data: GroupUpdatePayload): Promise<GroupRead> {
  return apiCall(async (client) => {
    const updated = await client.updateGroup(resolveActualId("group", _gid), {
      name: _data.name ?? undefined,
    });
    return {
      gid: rememberLegacyStringId("group", updated.id),
      name: updated.name,
      owner_uid: updated.owner_user_id ? rememberLegacyStringId("user", updated.owner_user_id) : "",
      parent_group_id: null,
      group_path: null,
      invite_quota_remaining: null,
      invite_quota_unlimited: null,
      description: null,
      created_at: updated.created_at,
      updated_at: updated.created_at,
    };
  });
}

export function deleteGroup(_gid: string) {
  return apiCall(async (client) => {
    await client.deleteGroup(resolveActualId("group", _gid));
  });
}

export function listGroupMembers(gid: string, page: number, page_size: number): Promise<PageResp<GroupMemberRead>> {
  return apiCall(async (client) => {
    const items = (await client.listGroupMembers(resolveActualId("group", gid))).map((item) => ({
      id: rememberLegacyId("group-member", item.id),
      group_id: rememberLegacyStringId("group", item.group_id),
      user_uid: rememberLegacyStringId("user", item.user_id),
      created_at: item.created_at,
    }));
    return makePage(items, page, page_size);
  });
}

export function addGroupMember(gid: string, user_uid: string): Promise<GroupMemberRead> {
  return apiCall(async (client) => {
    const item = await client.addGroupMember(resolveActualId("group", gid), {
      user_id: resolveActualId("user", user_uid),
      member_role: "member",
    });
    return {
      id: rememberLegacyId("group-member", item.id),
      group_id: rememberLegacyStringId("group", item.group_id),
      user_uid: rememberLegacyStringId("user", item.user_id),
      created_at: item.created_at,
    };
  });
}

export function removeGroupMember(_gid: string, _user_uid: string) {
  return apiCall(async (client) => {
    const item = await client.removeGroupMember(resolveActualId("group", _gid), resolveActualId("user", _user_uid));
    return {
      id: rememberLegacyId("group-member", item.id),
      group_id: rememberLegacyStringId("group", item.group_id),
      user_uid: rememberLegacyStringId("user", item.user_id),
      created_at: item.created_at,
    };
  });
}

export function getGroupInviteSummary(gid: string): Promise<InviteSummary> {
  return apiCall(async (client) => {
    const summary = await client.getGroupInviteSummary(resolveActualId("group", gid));
    return {
      target_type: "GROUP",
      target_id: rememberLegacyStringId("group", summary.target_id),
      invite_quota_remaining: summary.invite_quota_remaining,
      invite_quota_unlimited: summary.invite_quota_unlimited,
    };
  });
}
