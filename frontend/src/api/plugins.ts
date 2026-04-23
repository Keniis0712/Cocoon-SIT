import { apiJson } from "./client";
import { resolveActualId } from "./id-map";
import type { PluginTargetBindingRead, UserPluginRead } from "./types/plugins";

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

export function listWorkspacePluginTargetBindings(pluginId: string): Promise<PluginTargetBindingRead[]> {
  return apiJson<PluginTargetBindingRead[]>(`/plugins/${pluginId}/targets`);
}

export function addWorkspacePluginTargetBinding(
  pluginId: string,
  targetType: "cocoon" | "chat_group",
  targetId: string,
): Promise<PluginTargetBindingRead> {
  return apiJson<PluginTargetBindingRead>(`/plugins/${pluginId}/targets`, {
    method: "POST",
    body: JSON.stringify({
      target_type: targetType,
      target_id: targetType === "cocoon" ? resolveActualId("cocoon", targetId) : targetId,
    }),
  });
}

export function deleteWorkspacePluginTargetBinding(
  pluginId: string,
  bindingId: string,
): Promise<{ deleted: boolean }> {
  return apiJson<{ deleted: boolean }>(`/plugins/${pluginId}/targets/${bindingId}`, {
    method: "DELETE",
  });
}
