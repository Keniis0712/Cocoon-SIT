import { apiCall, apiJson } from "./client";
import { rememberLegacyId, rememberLegacyStringId, resolveActualId } from "./id-map";
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

type GroupResponse = {
  id: string;
  name: string;
  owner_user_id: string | null;
  parent_group_id: string | null;
  group_path: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

function mapGroup(item: GroupResponse): GroupRead {
  return {
    gid: rememberLegacyStringId("group", item.id),
    name: item.name,
    owner_uid: item.owner_user_id ? rememberLegacyStringId("user", item.owner_user_id) : "",
    parent_group_id: item.parent_group_id ? rememberLegacyStringId("group", item.parent_group_id) : null,
    group_path: item.group_path,
    invite_quota_remaining: null,
    invite_quota_unlimited: null,
    description: item.description,
    created_at: item.created_at,
    updated_at: item.updated_at,
  };
}

export function listGroups(page: number, page_size: number, params?: { q?: string }): Promise<PageResp<GroupRead>> {
  return apiCall(async () => {
    const items = (await apiJson<GroupResponse[]>("/groups"))
      .map(mapGroup)
      .filter((item) => !params?.q || item.name.includes(params.q));
    return makePage(items, page, page_size);
  });
}

export function createGroup(data: GroupCreatePayload): Promise<GroupRead> {
  return apiCall(async () => {
    const group = await apiJson<GroupResponse>("/groups", {
      method: "POST",
      body: JSON.stringify({
        name: data.name.trim(),
        parent_group_id: data.parent_group_id ? resolveActualId("group", data.parent_group_id) : null,
        description: data.description ?? null,
      }),
    });
    return mapGroup(group);
  });
}

export function updateGroup(gid: string, data: GroupUpdatePayload): Promise<GroupRead> {
  return apiCall(async () => {
    const updated = await apiJson<GroupResponse>(`/groups/${resolveActualId("group", gid)}`, {
      method: "PATCH",
      body: JSON.stringify({
        name: data.name ?? undefined,
        parent_group_id:
          data.parent_group_id === undefined
            ? undefined
            : data.parent_group_id
              ? resolveActualId("group", data.parent_group_id)
              : null,
        description: data.description === undefined ? undefined : data.description,
      }),
    });
    return mapGroup(updated);
  });
}

export function deleteGroup(gid: string) {
  return apiCall(async (client) => {
    await client.deleteGroup(resolveActualId("group", gid));
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

export function removeGroupMember(gid: string, user_uid: string) {
  return apiCall(async (client) => {
    const item = await client.removeGroupMember(resolveActualId("group", gid), resolveActualId("user", user_uid));
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
