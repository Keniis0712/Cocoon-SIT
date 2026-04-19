import { apiCall } from "./client";
import { rememberLegacyId, resolveActualId } from "./id-map";
import type { TagPayload, TagRead } from "./types";

function mapTag(item: {
  id: string;
  tag_id: string;
  brief: string;
  is_isolated: boolean;
  meta_json: Record<string, unknown>;
  created_at: string;
}): TagRead {
  const meta = item.meta_json || {};
  return {
    id: rememberLegacyId("tag", item.id),
    tag_id: item.tag_id,
    owner_uid: null,
    name: item.tag_id,
    brief: item.brief,
    priority: typeof meta.priority === "number" ? meta.priority : 0,
    visibility_mode: item.is_isolated ? "private" : "public",
    group_allowlist_json: JSON.stringify(meta.group_allowlist ?? []),
    group_denylist_json: JSON.stringify(meta.group_denylist ?? []),
    created_at: item.created_at,
    updated_at: item.created_at,
  };
}

export function listTags() {
  return apiCall(async (client) => (await client.listTags()).map(mapTag));
}

export function createTag(payload: TagPayload) {
  return apiCall(async (client) => {
    const created = await client.createTag({
      tag_id: payload.name.trim(),
      brief: payload.brief || "",
      is_isolated: payload.visibility_mode !== "public",
      meta_json: {
        priority: payload.priority || 0,
        group_allowlist: payload.group_allowlist || [],
        group_denylist: payload.group_denylist || [],
      },
    });
    return mapTag(created);
  });
}

export function updateTag(tagId: number, payload: Partial<TagPayload>) {
  return apiCall(async (client) => {
    const updated = await client.updateTag(resolveActualId("tag", tagId), {
      brief: payload.brief || "",
      is_isolated: payload.visibility_mode ? payload.visibility_mode !== "public" : false,
      meta_json: {
        priority: payload.priority || 0,
        group_allowlist: payload.group_allowlist || [],
        group_denylist: payload.group_denylist || [],
      },
    });
    return mapTag(updated);
  });
}

export function deleteTag(tagId: number) {
  return apiCall(async (client) => {
    const deleted = await client.deleteTag(resolveActualId("tag", tagId));
    return mapTag(deleted);
  });
}

export function bindCocoonTags(cocoonId: number, tagIds: number[]) {
  return apiCall(async (client) => {
    const actualCocoonId = resolveActualId("cocoon", cocoonId);
    const existing = await client.listCocoonTags(actualCocoonId);
    const existingIds = new Set(existing.map((item) => item.tag_id));
    const desiredIds = tagIds.map((item) => resolveActualId("tag", item));

    for (const tagId of desiredIds) {
      if (!existingIds.has(tagId)) {
        await client.bindCocoonTag(actualCocoonId, { tag_id: tagId });
      }
    }

    for (const tagId of existingIds) {
      if (!desiredIds.includes(tagId)) {
        await client.unbindCocoonTag(actualCocoonId, tagId);
      }
    }

    const [tags, bindings] = await Promise.all([client.listTags(), client.listCocoonTags(actualCocoonId)]);
    const tagMap = new Map(tags.map((item) => [item.id, mapTag(item)] as const));
    return bindings.map((binding) => tagMap.get(binding.tag_id)).filter(Boolean) as TagRead[];
  });
}
