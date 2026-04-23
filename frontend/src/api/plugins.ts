import { apiJson } from "./client";
import type { UserPluginRead } from "./types/plugins";

export function listWorkspacePlugins(): Promise<UserPluginRead[]> {
  return apiJson<UserPluginRead[]>("/plugins");
}

export function getWorkspacePlugin(pluginId: string): Promise<UserPluginRead> {
  return apiJson<UserPluginRead>(`/plugins/${pluginId}`);
}

export function setWorkspacePluginEnabled(pluginId: string, enabled: boolean): Promise<UserPluginRead> {
  return apiJson<UserPluginRead>(`/plugins/${pluginId}/${enabled ? "enable" : "disable"}`, {
    method: "POST",
  });
}

export function updateWorkspacePluginConfig(
  pluginId: string,
  config_json: Record<string, unknown>,
): Promise<UserPluginRead> {
  return apiJson<UserPluginRead>(`/plugins/${pluginId}/config`, {
    method: "PATCH",
    body: JSON.stringify({ config_json }),
  });
}

export function validateWorkspacePluginConfig(pluginId: string): Promise<UserPluginRead> {
  return apiJson<UserPluginRead>(`/plugins/${pluginId}/validate`, {
    method: "POST",
  });
}

export function clearWorkspacePluginError(pluginId: string): Promise<UserPluginRead> {
  return apiJson<UserPluginRead>(`/plugins/${pluginId}/clear-error`, {
    method: "POST",
  });
}
