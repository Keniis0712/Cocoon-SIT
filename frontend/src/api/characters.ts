import { apiCall, apiJson } from "./client";
import {
  rememberLegacyId,
  rememberLegacyStringId,
  resolveActualId,
} from "./id-map";
import type { PageResp } from "./types/common";
import type {
  CharacterAclEffectiveEntry,
  CharacterAclEntryRead,
  CharacterAclEntryWrite,
  CharacterPayload,
  CharacterRead,
} from "./types/catalog";

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

function numericId(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash || 1;
}

function mapCharacter(item: {
  id: string;
  name: string;
  prompt_summary: string;
  settings_json: Record<string, unknown>;
  created_by_user_id: string | null;
  created_at: string;
}): CharacterRead {
  const settings = item.settings_json || {};
  return {
    id: rememberLegacyId("character", item.id),
    name: item.name,
    owner_uid: item.created_by_user_id ? rememberLegacyStringId("user", item.created_by_user_id) : null,
    visibility: settings.visibility === "public" ? "public" : "private",
    description: typeof settings.description === "string" ? settings.description : null,
    personality_prompt:
      typeof settings.personality_prompt === "string" ? settings.personality_prompt : item.prompt_summary,
    created_at: item.created_at,
  };
}

function mapAcl(item: {
  id: string;
  character_id: string;
  subject_type: string;
  subject_id: string;
  can_read: boolean;
  can_use: boolean;
  created_at: string;
  updated_at?: string;
}): CharacterAclEntryRead {
  return {
    id: numericId(item.id),
    character_id: rememberLegacyId("character", item.character_id),
    grantee_type: item.subject_type as CharacterAclEntryRead["grantee_type"],
    grantee_id:
      item.subject_type === "USER"
        ? rememberLegacyStringId("user", item.subject_id)
        : item.subject_type === "GROUP"
          ? rememberLegacyStringId("group", item.subject_id)
          : item.subject_id,
    perm_level: item.can_use ? 2 : item.can_read ? 1 : 0,
    granted_by_uid: null,
    created_at: item.created_at,
    updated_at: item.updated_at || item.created_at,
  };
}

export function getCharacters(
  page: number,
  page_size: number,
  scope: "basic_visible" | "inherited_visible" | "manageable" = "inherited_visible",
): Promise<PageResp<CharacterRead>> {
  return apiCall(async () => {
    const items = (await apiJson<any[]>(`/characters?scope=${scope}`)).map(mapCharacter);
    return makePage(items, page, page_size);
  });
}

export function getCharacter(id: number): Promise<CharacterRead> {
  return apiCall(async () => {
    const actualId = resolveActualId("character", id);
    const [visible, manageable] = await Promise.all([
      apiJson<any[]>("/characters?scope=inherited_visible"),
      apiJson<any[]>("/characters?scope=manageable"),
    ]);
    const found = [...visible, ...manageable].find((item) => item.id === actualId);
    if (!found) {
      throw new Error("Character not found");
    }
    return mapCharacter(found);
  });
}

export function createCharacter(data: CharacterPayload): Promise<CharacterRead> {
  return apiCall(async (client) => {
    const created = await client.createCharacter({
      name: data.name.trim(),
      prompt_summary: data.personality_prompt.trim(),
      settings_json: {
        description: data.description ?? null,
        personality_prompt: data.personality_prompt.trim(),
        visibility: data.visibility || "private",
      },
    });
    return mapCharacter(created);
  });
}

export function updateCharacter(id: number, data: Partial<CharacterPayload>): Promise<CharacterRead> {
  return apiCall(async (client) => {
    const updated = await client.updateCharacter(resolveActualId("character", id), {
      name: data.name?.trim(),
      prompt_summary: data.personality_prompt?.trim(),
      settings_json: {
        description: data.description ?? null,
        personality_prompt: data.personality_prompt?.trim(),
        visibility: data.visibility || "private",
      },
    });
    return mapCharacter(updated);
  });
}

export function deleteCharacter(_id: number) {
  return apiCall(async (client) => {
    return mapCharacter(await client.deleteCharacter(resolveActualId("character", _id)));
  });
}

export function getCharacterAcl(characterId: number): Promise<CharacterAclEntryRead[]> {
  return apiCall(async (client) => {
    return (await client.listCharacterAcl(resolveActualId("character", characterId))).map(mapAcl);
  });
}

export function appendCharacterAclEntries(
  characterId: number,
  entries: CharacterAclEntryWrite[],
): Promise<CharacterAclEntryRead[]> {
  return apiCall(async (client) => {
    const actualId = resolveActualId("character", characterId);
    for (const entry of entries) {
      await client.createCharacterAcl(actualId, {
        subject_type: entry.grantee_type,
        subject_id:
          entry.grantee_type === "USER"
            ? resolveActualId("user", entry.grantee_id)
            : entry.grantee_type === "GROUP"
              ? resolveActualId("group", entry.grantee_id)
              : entry.grantee_id,
        can_read: true,
        can_use: entry.perm_level !== "READ",
      });
    }
    return (await client.listCharacterAcl(actualId)).map(mapAcl);
  });
}

export function deleteCharacterAclEntry(
  _characterId: number,
  _granteeType: string,
  _granteeId: string,
) {
  return apiCall(async (client) => {
    const entries = await client.listCharacterAcl(resolveActualId("character", _characterId));
    const matched = entries.find((item) => {
      const subjectType = item.subject_type;
      const rawSubjectId =
        subjectType === "USER"
          ? rememberLegacyStringId("user", item.subject_id)
          : subjectType === "GROUP"
            ? rememberLegacyStringId("group", item.subject_id)
            : item.subject_id;
      return subjectType === _granteeType && rawSubjectId === _granteeId;
    });
    if (!matched) {
      throw new Error("Character ACL entry not found");
    }
    return mapAcl(
      await client.deleteCharacterAcl(
        resolveActualId("character", _characterId),
        String(matched.id),
      ),
    );
  });
}

export function getCharacterEffectiveAcl(
  characterId: number,
  params?: { user_uid?: string; group_id?: string },
): Promise<CharacterAclEffectiveEntry[]> {
  return getCharacterAcl(characterId).then((items) =>
    items
      .filter((item) => {
        if (params?.user_uid) {
          return item.grantee_type === "USER" && item.grantee_id === params.user_uid;
        }
        if (params?.group_id) {
          return item.grantee_type === "GROUP" && item.grantee_id === params.group_id;
        }
        return true;
      })
      .map((item) => ({
        source: item.grantee_type,
        grantee_id: item.grantee_id,
        perm_level: item.perm_level,
      })),
  );
}
