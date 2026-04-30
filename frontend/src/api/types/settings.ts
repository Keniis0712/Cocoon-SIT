export interface SystemSettingsRead {
  allow_registration: boolean;
  max_chat_turns: number;
  allowed_model_ids: number[];
  default_max_context_messages: number;
  default_auto_compaction_enabled: boolean;
  private_chat_debounce_seconds: number;
  group_chat_debounce_seconds: number;
  rollback_retention_days: number;
  rollback_cleanup_interval_hours: number;
  default_memory_profile: string;
  memory_profiles_json: Record<string, Record<string, unknown>>;
  created_at: string;
  updated_at: string;
}

export interface SystemSettingsUpdate {
  allow_registration?: boolean;
  max_chat_turns?: number;
  allowed_model_ids?: number[];
  default_max_context_messages?: number;
  default_auto_compaction_enabled?: boolean;
  private_chat_debounce_seconds?: number;
  group_chat_debounce_seconds?: number;
  rollback_retention_days?: number;
  rollback_cleanup_interval_hours?: number;
  default_memory_profile?: string;
  memory_profiles_json?: Record<string, Record<string, unknown>>;
}
