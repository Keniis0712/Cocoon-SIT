import { apiCall } from "./client";
import { rememberLegacyId, resolveActualId } from "./id-map";
import type { SystemSettingsRead, SystemSettingsUpdate } from "./types";

function mapSettings(item: {
  allow_registration: boolean;
  max_chat_turns: number;
  allowed_model_ids: string[];
  default_cocoon_temperature: number;
  default_max_context_messages: number;
  default_auto_compaction_enabled: boolean;
  private_chat_debounce_seconds: number;
  rollback_retention_days: number;
  rollback_cleanup_interval_hours: number;
  created_at: string;
  updated_at: string;
}): SystemSettingsRead {
  return {
    allow_registration: item.allow_registration,
    max_chat_turns: item.max_chat_turns,
    allowed_model_ids: (item.allowed_model_ids || []).map((modelId) => rememberLegacyId("model", modelId)),
    default_cocoon_temperature: item.default_cocoon_temperature,
    default_max_context_messages: item.default_max_context_messages,
    default_auto_compaction_enabled: item.default_auto_compaction_enabled,
    private_chat_debounce_seconds: item.private_chat_debounce_seconds,
    rollback_retention_days: item.rollback_retention_days,
    rollback_cleanup_interval_hours: item.rollback_cleanup_interval_hours,
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
