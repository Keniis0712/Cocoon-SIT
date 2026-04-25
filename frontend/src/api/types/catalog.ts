export interface CharacterRead {
  id: number;
  name: string;
  owner_uid: string | null;
  visibility: "private" | "public" | string;
  description: string | null;
  personality_prompt: string;
  created_at: string;
}

export interface CharacterPayload {
  name: string;
  description?: string | null;
  personality_prompt: string;
  visibility?: "private" | "public";
}

export interface CharacterAclEntryRead {
  id: number;
  character_id: number;
  grantee_type: "USER" | "GROUP" | "SUBTREE" | "AUTHENTICATED_ALL" | string;
  grantee_id: string;
  perm_level: number;
  granted_by_uid: string | null;
  created_at: string;
  updated_at: string;
}

export interface CharacterAclEntryWrite {
  grantee_type: "USER" | "GROUP" | "SUBTREE" | "AUTHENTICATED_ALL";
  grantee_id: string;
  perm_level: "READ" | "USE" | "MANAGE";
}

export interface CharacterAclEffectiveEntry {
  source: string;
  grantee_id: string | null;
  perm_level: number;
}

export interface TagRead {
  id: number;
  actual_id: string;
  tag_id: string;
  name: string;
  brief: string;
  visibility_mode: "public" | "private" | "group_acl" | string;
  is_system: boolean;
  visible_chat_group_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface TagPayload {
  name: string;
  brief?: string;
  visibility_mode?: "public" | "private" | "group_acl" | string;
  visible_chat_group_ids?: string[];
}
