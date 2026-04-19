export interface ChatGroupRead {
  id: string;
  name: string;
  owner_user_id: string;
  character_id: string;
  selected_model_id: string;
  default_temperature: number;
  max_context_messages: number;
  auto_compaction_enabled: boolean;
  external_platform: string | null;
  external_group_id: string | null;
  external_account_id: string | null;
  created_at: string;
}

export interface ChatGroupPayload {
  name: string;
  character_id: number;
  selected_model_id: number;
  default_temperature?: number | null;
  max_context_messages?: number | null;
  auto_compaction_enabled?: boolean | null;
  external_platform?: string | null;
  external_group_id?: string | null;
  external_account_id?: string | null;
  initial_member_ids?: string[];
}

export interface ChatGroupUpdatePayload {
  name?: string;
  character_id?: number | null;
  selected_model_id?: number | null;
  default_temperature?: number | null;
  max_context_messages?: number | null;
  auto_compaction_enabled?: boolean | null;
  external_platform?: string | null;
  external_group_id?: string | null;
  external_account_id?: string | null;
}

export interface ChatGroupMemberRead {
  id: string;
  room_id: string;
  user_id: string;
  member_role: "admin" | "member" | string;
  created_at: string;
}

export interface ChatGroupStateRead {
  id: string;
  cocoon_id: string | null;
  chat_group_id: string;
  relation_score: number;
  persona_json: Record<string, unknown>;
  active_tags_json: string[];
  current_wakeup_task_id: string | null;
}

