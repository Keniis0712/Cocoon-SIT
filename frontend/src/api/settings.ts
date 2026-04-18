import { unsupportedFeature } from "./client";
import type { SystemSettingsRead, SystemSettingsUpdate } from "./types";

const DEFAULT_SETTINGS: SystemSettingsRead = {
  allow_registration: false,
  max_chat_turns: 0,
  allowed_model_ids: [],
  default_max_context_tokens: 0,
  default_max_rounds: 0,
  default_compact_memory_max_items: 0,
  default_auto_compaction_trigger_rounds: 0,
  default_auto_compaction_message_count: 0,
  default_auto_compaction_memory_max_items: 0,
  default_manual_compaction_message_count: 0,
  default_manual_compaction_memory_max_items: 0,
  default_manual_compaction_mode: "all",
  dispatch_thread_pool_max_workers: 0,
  llm_max_concurrency: 0,
  embedding_max_concurrency: 0,
  private_chat_debounce_ms: 0,
  group_chat_debounce_ms: 0,
  typing_debounce_max_extra_ms: 0,
  idle_followup_medium_turn_threshold: 0,
  idle_followup_high_turn_threshold: 0,
  idle_followup_low_activity_seconds: 0,
  idle_followup_medium_activity_seconds: 0,
  idle_followup_high_activity_seconds: 0,
  rollback_retention_days: 0,
  rollback_cleanup_interval_hours: 0,
  created_at: "",
  updated_at: "",
};

export function getSystemSettings(): Promise<SystemSettingsRead> {
  return Promise.resolve(DEFAULT_SETTINGS);
}

export function updateSystemSettings(_data: SystemSettingsUpdate): Promise<SystemSettingsRead> {
  return unsupportedFeature("System settings are not exposed by the current backend");
}

export function triggerRollbackCleanup(): Promise<Record<string, number>> {
  return unsupportedFeature("Rollback cleanup is not exposed by the current backend");
}
