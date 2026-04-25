import { apiJson } from "./client";
import { rememberLegacyId, resolveActualId } from "./id-map";
import type { TagPayload, TagRead } from "./types";

type RawTag = {
  id: string;
  tag_id: string;
  brief: string;
  visibility: string;
  is_system: boolean;
  visible_chat_group_ids: string[];
  created_at: string;
};

type RawBinding = {
  id: string;
  tag_id: string;
  created_at: string;
};

function mapTag(item: RawTag): TagRead {
  return {
    id: rememberLegacyId("tag", item.id),
    actual_id: item.id,
    tag_id: item.tag_id,
    name: item.tag_id,
    brief: item.brief,
    visibility_mode: item.visibility || "private",
    is_system: Boolean(item.is_system),
    visible_chat_group_ids: item.visible_chat_group_ids ?? [],
    created_at: item.created_at,
    updated_at: item.created_at,
  };
}

export function listTags() {
  return apiJson<RawTag[]>("/tags").then((items) => items.map(mapTag));
}

export function createTag(payload: TagPayload) {
  return apiJson<RawTag>("/tags", {
    method: "POST",
    body: JSON.stringify({
      tag_id: payload.name.trim(),
      brief: payload.brief || "",
      visibility: payload.visibility_mode || "private",
      is_isolated: payload.visibility_mode === "private",
      meta_json: {},
      visible_chat_group_ids: payload.visible_chat_group_ids || [],
    }),
  }).then(mapTag);
}

export function updateTag(tagId: number, payload: Partial<TagPayload>) {
  return apiJson<RawTag>(`/tags/${resolveActualId("tag", tagId)}`, {
    method: "PATCH",
    body: JSON.stringify({
      brief: payload.brief,
      visibility: payload.visibility_mode,
      is_isolated: payload.visibility_mode ? payload.visibility_mode === "private" : undefined,
      meta_json: {},
      visible_chat_group_ids: payload.visible_chat_group_ids,
    }),
  }).then(mapTag);
}

export function deleteTag(tagId: number) {
  return apiJson<RawTag>(`/tags/${resolveActualId("tag", tagId)}`, {
    method: "DELETE",
  }).then(mapTag);
}

async function reconcileTargetTags(
  listPath: string,
  bindPath: string,
  unbindPath: (tagId: string) => string,
  tagIds: number[],
) {
  const existing = await apiJson<RawBinding[]>(listPath);
  const existingIds = new Set(existing.map((item) => item.tag_id));
  const desiredIds = tagIds.map((item) => resolveActualId("tag", item));

  for (const tagId of desiredIds) {
    if (!existingIds.has(tagId)) {
      await apiJson(bindPath, {
        method: "POST",
        body: JSON.stringify({ tag_id: tagId }),
      });
    }
  }

  for (const tagId of existingIds) {
    if (!desiredIds.includes(tagId)) {
      await apiJson(unbindPath(tagId), {
        method: "DELETE",
      });
    }
  }

  const [tags, bindings] = await Promise.all([listTags(), apiJson<RawBinding[]>(listPath)]);
  const tagMap = new Map(tags.map((item) => [item.actual_id, item] as const));
  return bindings.map((binding) => tagMap.get(binding.tag_id)).filter(Boolean) as TagRead[];
}

export function bindCocoonTags(cocoonId: number, tagIds: number[]) {
  const actualCocoonId = resolveActualId("cocoon", cocoonId);
  return reconcileTargetTags(
    `/cocoons/${actualCocoonId}/tags`,
    `/cocoons/${actualCocoonId}/tags`,
    (tagId) => `/cocoons/${actualCocoonId}/tags/${tagId}`,
    tagIds,
  );
}

export function bindChatGroupTags(roomId: string, tagIds: number[]) {
  return reconcileTargetTags(
    `/chat-groups/${roomId}/tags`,
    `/chat-groups/${roomId}/tags`,
    (tagId) => `/chat-groups/${roomId}/tags/${tagId}`,
    tagIds,
  );
}
