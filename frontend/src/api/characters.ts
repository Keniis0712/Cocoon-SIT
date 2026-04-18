import { apiCall, unsupportedFeature } from "./client";
import {
  rememberLegacyId,
  rememberLegacyStringId,
  resolveActualId,
} from "./id-map";
import type {
  CharacterAclEffectiveEntry,
  CharacterAclEntryRead,
  CharacterAclEntryWrite,
  CharacterPayload,
  CharacterRead,
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
  _scope: "mine" | "all" = "mine",
): Promise<PageResp<CharacterRead>> {
  return apiCall(async (client) => {
    const items = (await client.listCharacters()).map(mapCharacter);
    return makePage(items, page, page_size);
  });
}

export function getCharacter(id: number): Promise<CharacterRead> {
  return apiCall(async (client) => {
    const all = await client.listCharacters();
    const found = all.find((item) => item.id === resolveActualId("character", id));
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
  return unsupportedFeature("Deleting characters is not supported by the current backend");
}

export function getCharacterAcl(characterId: number): Promise<CharacterAclEntryRead[]> {
  return apiCall(async (client) => {
    return (await client.listCharacterAcl(resolveActualId("character", characterId))).map(mapAcl);
  });
}

export function replaceCharacterAcl(
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
  return unsupportedFeature("Removing character ACL entries is not supported by the current backend");
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
