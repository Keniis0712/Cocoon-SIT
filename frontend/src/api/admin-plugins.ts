import { apiJson } from "./client";
import { resolveActualId } from "./id-map";
import type {
  AdminPluginDetailRead,
  AdminPluginListItemRead,
  AdminPluginSharedPackageRead,
  PluginGroupVisibilityRead,
} from "./types/plugins";

function encodePath(value: string) {
  return encodeURIComponent(value);
}

export function listAdminPlugins(): Promise<AdminPluginListItemRead[]> {
  return apiJson<AdminPluginListItemRead[]>("/admin/plugins");
}

export function getAdminPlugin(pluginId: string): Promise<AdminPluginDetailRead> {
  return apiJson<AdminPluginDetailRead>(`/admin/plugins/${pluginId}`);
}

export function listAdminPluginSharedPackages(): Promise<AdminPluginSharedPackageRead[]> {
  return apiJson<AdminPluginSharedPackageRead[]>("/admin/plugins/shared-libs");
}

export function installAdminPlugin(file: File): Promise<AdminPluginDetailRead> {
  const payload = new FormData();
  payload.append("file", file);
  return apiJson<AdminPluginDetailRead>("/admin/plugins/install", {
    method: "POST",
    body: payload,
  });
}

export function updateAdminPlugin(pluginId: string, file: File): Promise<AdminPluginDetailRead> {
  const payload = new FormData();
  payload.append("file", file);
  return apiJson<AdminPluginDetailRead>(`/admin/plugins/${pluginId}/update`, {
    method: "POST",
    body: payload,
  });
}

export function setAdminPluginEnabled(pluginId: string, enabled: boolean): Promise<AdminPluginDetailRead> {
  return apiJson<AdminPluginDetailRead>(`/admin/plugins/${pluginId}/${enabled ? "enable" : "disable"}`, {
    method: "POST",
  });
}

export function deleteAdminPlugin(pluginId: string): Promise<{ deleted: boolean }> {
  return apiJson<{ deleted: boolean }>(`/admin/plugins/${pluginId}`, {
    method: "DELETE",
  });
}

export function updateAdminPluginConfig(
  pluginId: string,
  config_json: Record<string, unknown>,
): Promise<AdminPluginDetailRead> {
  return apiJson<AdminPluginDetailRead>(`/admin/plugins/${pluginId}/config`, {
    method: "PATCH",
    body: JSON.stringify({ config_json }),
  });
}

export function validateAdminPluginConfig(
  pluginId: string,
  config_json: Record<string, unknown>,
): Promise<AdminPluginDetailRead> {
  return apiJson<AdminPluginDetailRead>(`/admin/plugins/${pluginId}/config/validate`, {
    method: "POST",
    body: JSON.stringify({ config_json }),
  });
}

export function updateAdminPluginEventConfig(
  pluginId: string,
  eventName: string,
  config_json: Record<string, unknown>,
): Promise<AdminPluginDetailRead> {
  return apiJson<AdminPluginDetailRead>(
    `/admin/plugins/${pluginId}/events/${encodePath(eventName)}/config`,
    {
      method: "PATCH",
      body: JSON.stringify({ config_json }),
    },
  );
}

export function updateAdminPluginEventSchedule(
  pluginId: string,
  eventName: string,
  payload: {
    schedule_mode: "manual" | "interval" | "cron";
    schedule_interval_seconds?: number | null;
    schedule_cron?: string | null;
  },
): Promise<AdminPluginDetailRead> {
  return apiJson<AdminPluginDetailRead>(
    `/admin/plugins/${pluginId}/events/${encodePath(eventName)}/schedule`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
}

export function runAdminPluginEventNow(
  pluginId: string,
  eventName: string,
): Promise<AdminPluginDetailRead> {
  return apiJson<AdminPluginDetailRead>(
    `/admin/plugins/${pluginId}/events/${encodePath(eventName)}/run`,
    {
      method: "POST",
    },
  );
}

export function setAdminPluginEventEnabled(
  pluginId: string,
  eventName: string,
  enabled: boolean,
): Promise<AdminPluginDetailRead> {
  return apiJson<AdminPluginDetailRead>(
    `/admin/plugins/${pluginId}/events/${encodePath(eventName)}/${enabled ? "enable" : "disable"}`,
    {
      method: "POST",
    },
  );
}

export function setAdminPluginGlobalVisibility(
  pluginId: string,
  is_globally_visible: boolean,
): Promise<AdminPluginDetailRead> {
  return apiJson<AdminPluginDetailRead>(`/admin/plugins/${pluginId}/visibility`, {
    method: "PATCH",
    body: JSON.stringify({ is_globally_visible }),
  });
}

export function listAdminPluginGroupVisibility(pluginId: string): Promise<PluginGroupVisibilityRead[]> {
  return apiJson<PluginGroupVisibilityRead[]>(`/admin/plugins/${pluginId}/groups/visibility`);
}

export function setAdminPluginGroupVisibility(
  pluginId: string,
  groupId: string,
  is_visible: boolean,
): Promise<PluginGroupVisibilityRead> {
  return apiJson<PluginGroupVisibilityRead>(
    `/admin/plugins/${pluginId}/groups/${resolveActualId("group", groupId)}/visibility`,
    {
      method: "PUT",
      body: JSON.stringify({ is_visible }),
    },
  );
}
