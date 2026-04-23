import { apiJson } from "./client";
import { resolveActualId } from "./id-map";
import type { ChatGroupPluginConfigRead, PluginTargetBindingRead, UserPluginRead } from "./types/plugins";

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

export function getChatGroupPluginConfig(
  pluginId: string,
  chatGroupId: string,
): Promise<ChatGroupPluginConfigRead> {
  return apiJson<ChatGroupPluginConfigRead>(`/plugins/${pluginId}/chat-groups/${chatGroupId}/config`);
}

export function setChatGroupPluginEnabled(
  pluginId: string,
  chatGroupId: string,
  enabled: boolean,
): Promise<ChatGroupPluginConfigRead> {
  return apiJson<ChatGroupPluginConfigRead>(
    `/plugins/${pluginId}/chat-groups/${chatGroupId}/${enabled ? "enable" : "disable"}`,
    { method: "POST" },
  );
}

export function updateChatGroupPluginConfig(
  pluginId: string,
  chatGroupId: string,
  config_json: Record<string, unknown>,
): Promise<ChatGroupPluginConfigRead> {
  return apiJson<ChatGroupPluginConfigRead>(`/plugins/${pluginId}/chat-groups/${chatGroupId}/config`, {
    method: "PATCH",
    body: JSON.stringify({ config_json }),
  });
}

export function validateChatGroupPluginConfig(
  pluginId: string,
  chatGroupId: string,
): Promise<ChatGroupPluginConfigRead> {
  return apiJson<ChatGroupPluginConfigRead>(`/plugins/${pluginId}/chat-groups/${chatGroupId}/validate`, {
    method: "POST",
  });
}

export function clearChatGroupPluginError(
  pluginId: string,
  chatGroupId: string,
): Promise<ChatGroupPluginConfigRead> {
  return apiJson<ChatGroupPluginConfigRead>(`/plugins/${pluginId}/chat-groups/${chatGroupId}/clear-error`, {
    method: "POST",
  });
}
