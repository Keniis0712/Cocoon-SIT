import { apiCall } from "./client";
import { rememberLegacyId, resolveActualId } from "./id-map";
import type { SystemSettingsRead, SystemSettingsUpdate } from "./types/settings";

function mapSettings(item: {
  allow_registration: boolean;
  max_chat_turns: number;
  allowed_model_ids: string[];
  default_max_context_messages: number;
  default_auto_compaction_enabled: boolean;
  private_chat_debounce_seconds: number;
  group_chat_debounce_seconds?: number;
  rollback_retention_days: number;
  rollback_cleanup_interval_hours: number;
  default_memory_profile?: string;
  memory_profiles_json?: Record<string, Record<string, unknown>>;
  created_at: string;
  updated_at: string;
}): SystemSettingsRead {
  return {
    allow_registration: item.allow_registration,
    max_chat_turns: item.max_chat_turns,
    allowed_model_ids: (item.allowed_model_ids || []).map((modelId) => rememberLegacyId("model", modelId)),
    default_max_context_messages: item.default_max_context_messages,
    default_auto_compaction_enabled: item.default_auto_compaction_enabled,
    private_chat_debounce_seconds: item.private_chat_debounce_seconds,
    group_chat_debounce_seconds: item.group_chat_debounce_seconds ?? 0,
    rollback_retention_days: item.rollback_retention_days,
    rollback_cleanup_interval_hours: item.rollback_cleanup_interval_hours,
    default_memory_profile: item.default_memory_profile ?? "meta_reply",
    memory_profiles_json: item.memory_profiles_json ?? {},
    created_at: item.created_at,
    updated_at: item.updated_at,
  };
}

function serializeUpdate(data: SystemSettingsUpdate) {
  return {
    ...data,
    allowed_model_ids: data.allowed_model_ids?.map((modelId) => resolveActualId("model", modelId)),
  };
}

export function getSystemSettings(): Promise<SystemSettingsRead> {
  return apiCall(async (client) => mapSettings(await client.getSystemSettings()));
}

export function updateSystemSettings(data: SystemSettingsUpdate): Promise<SystemSettingsRead> {
  return apiCall(async (client) => mapSettings(await client.updateSystemSettings(serializeUpdate(data))));
}
