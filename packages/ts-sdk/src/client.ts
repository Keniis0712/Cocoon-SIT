import type { components } from "./generated";

export type Schemas = components["schemas"];

export interface ApiClientOptions {
  baseUrl: string;
  getAccessToken?: () => string | null | undefined;
  onUnauthorized?: () => void;
}

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, data: unknown) {
    super(typeof data === "string" ? data : `Request failed with status ${status}`);
    this.status = status;
    this.data = data;
  }
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
};

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

export class CocoonApiClient {
  private readonly baseUrl: string;
  private readonly getAccessToken?: () => string | null | undefined;
  private readonly onUnauthorized?: () => void;

  constructor(options: ApiClientOptions) {
    this.baseUrl = trimTrailingSlash(options.baseUrl);
    this.getAccessToken = options.getAccessToken;
    this.onUnauthorized = options.onUnauthorized;
  }

  private async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const headers = new Headers(options.headers ?? {});
    headers.set("Accept", "application/json");

    const token = this.getAccessToken?.();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    let body: BodyInit | undefined;
    if (options.body !== undefined) {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(options.body);
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      method: options.method ?? "GET",
      headers,
      body,
    });

    const raw = await response.text();
    const data = raw ? safeJson(raw) : null;
    if (!response.ok) {
      if (response.status === 401) {
        this.onUnauthorized?.();
      }
      throw new ApiError(response.status, data);
    }
    return data as T;
  }

  makeCocoonWsUrl(cocoonId: string): string {
    const url = new URL(`${this.baseUrl}/api/v1/cocoons/${cocoonId}/ws`);
    if (url.protocol === "https:") {
      url.protocol = "wss:";
    } else if (url.protocol === "http:") {
      url.protocol = "ws:";
    }

    const token = this.getAccessToken?.();
    if (token) {
      url.searchParams.set("access_token", token);
    }

    return url.toString();
  }

  health() {
    return this.request<Schemas["HealthResponse"]>("/api/v1/health");
  }

  login(body: Schemas["LoginRequest"]) {
    return this.request<Schemas["TokenPair"]>("/api/v1/auth/login", { method: "POST", body });
  }

  register(body: Schemas["RegisterRequest"]) {
    return this.request<Schemas["TokenPair"]>("/api/v1/auth/register", { method: "POST", body });
  }

  refresh(body: Schemas["RefreshRequest"]) {
    return this.request<Schemas["TokenPair"]>("/api/v1/auth/refresh", { method: "POST", body });
  }

  logout(body: Schemas["RefreshRequest"]) {
    return this.request<Schemas["MessageResponse"]>("/api/v1/auth/logout", { method: "POST", body });
  }

  me() {
    return this.request<Schemas["UserOut"]>("/api/v1/auth/me");
  }

  getPublicFeatures() {
    return this.request<Schemas["PublicFeaturesOut"]>("/api/v1/auth/features");
  }

  listUsers() {
    return this.request<Schemas["UserOut"][]>("/api/v1/users");
  }

  createUser(body: Schemas["UserCreate"]) {
    return this.request<Schemas["UserOut"]>("/api/v1/users", { method: "POST", body });
  }

  updateUser(userId: string, body: Schemas["UserUpdate"]) {
    return this.request<Schemas["UserOut"]>(`/api/v1/users/${userId}`, { method: "PATCH", body });
  }

  listRoles() {
    return this.request<Schemas["RoleOut"][]>("/api/v1/roles");
  }

  createRole(body: Schemas["RoleCreate"]) {
    return this.request<Schemas["RoleOut"]>("/api/v1/roles", { method: "POST", body });
  }

  updateRole(roleId: string, body: Schemas["RoleUpdate"]) {
    return this.request<Schemas["RoleOut"]>(`/api/v1/roles/${roleId}`, { method: "PATCH", body });
  }

  listInvites() {
    return this.request<Schemas["InviteOut"][]>("/api/v1/invites");
  }

  createInvite(body: Schemas["InviteCreate"]) {
    return this.request<Schemas["InviteOut"]>("/api/v1/invites", { method: "POST", body });
  }

  revokeInvite(code: string) {
    return this.request<Schemas["InviteRevokeResult"]>(`/api/v1/invites/${code}`, { method: "DELETE" });
  }

  listInviteGrants() {
    return this.request<Schemas["InviteGrantOut"][]>("/api/v1/invites/grants");
  }

  createInviteGrant(body: Schemas["InviteGrantCreate"]) {
    return this.request<Schemas["InviteGrantOut"]>("/api/v1/invites/grants", { method: "POST", body });
  }

  getMyInviteSummary() {
    return this.request<Schemas["InviteSummaryOut"]>("/api/v1/invites/summary/me");
  }

  getGroupInviteSummary(groupId: string) {
    return this.request<Schemas["InviteSummaryOut"]>(`/api/v1/invites/summary/groups/${groupId}`);
  }

  redeemInvite(code: string, body: Schemas["InviteRedeemRequest"]) {
    return this.request<Schemas["InviteRedeemResult"]>(`/api/v1/invites/${code}/redeem`, { method: "POST", body });
  }

  listGroups() {
    return this.request<Schemas["GroupOut"][]>("/api/v1/groups");
  }

  createGroup(body: Schemas["GroupCreate"]) {
    return this.request<Schemas["GroupOut"]>("/api/v1/groups", { method: "POST", body });
  }

  updateGroup(groupId: string, body: Schemas["GroupUpdate"]) {
    return this.request<Schemas["GroupOut"]>(`/api/v1/groups/${groupId}`, { method: "PATCH", body });
  }

  deleteGroup(groupId: string) {
    return this.request<Schemas["GroupOut"]>(`/api/v1/groups/${groupId}`, { method: "DELETE" });
  }

  listGroupMembers(groupId: string) {
    return this.request<Schemas["GroupMemberOut"][]>(`/api/v1/groups/${groupId}/members`);
  }

  addGroupMember(groupId: string, body: Schemas["GroupMemberCreate"]) {
    return this.request<Schemas["GroupMemberOut"]>(`/api/v1/groups/${groupId}/members`, {
      method: "POST",
      body,
    });
  }

  removeGroupMember(groupId: string, userId: string) {
    return this.request<Schemas["GroupMemberOut"]>(`/api/v1/groups/${groupId}/members/${userId}`, {
      method: "DELETE",
    });
  }

  listCharacters() {
    return this.request<Schemas["CharacterOut"][]>("/api/v1/characters");
  }

  createCharacter(body: Schemas["CharacterCreate"]) {
    return this.request<Schemas["CharacterOut"]>("/api/v1/characters", { method: "POST", body });
  }

  updateCharacter(characterId: string, body: Schemas["CharacterUpdate"]) {
    return this.request<Schemas["CharacterOut"]>(`/api/v1/characters/${characterId}`, {
      method: "PATCH",
      body,
    });
  }

  deleteCharacter(characterId: string) {
    return this.request<Schemas["CharacterOut"]>(`/api/v1/characters/${characterId}`, {
      method: "DELETE",
    });
  }

  listCharacterAcl(characterId: string) {
    return this.request<Schemas["CharacterAclOut"][]>(`/api/v1/characters/${characterId}/acl`);
  }

  createCharacterAcl(characterId: string, body: Schemas["CharacterAclCreate"]) {
    return this.request<Schemas["CharacterAclOut"]>(`/api/v1/characters/${characterId}/acl`, {
      method: "POST",
      body,
    });
  }

  deleteCharacterAcl(characterId: string, aclId: string) {
    return this.request<Schemas["CharacterAclOut"]>(`/api/v1/characters/${characterId}/acl/${aclId}`, {
      method: "DELETE",
    });
  }

  listProviders() {
    return this.request<Schemas["ModelProviderOut"][]>("/api/v1/providers");
  }

  createProvider(body: Schemas["ModelProviderCreate"]) {
    return this.request<Schemas["ModelProviderOut"]>("/api/v1/providers", { method: "POST", body });
  }

  updateProvider(providerId: string, body: Schemas["ModelProviderCreate"]) {
    return this.request<Schemas["ModelProviderOut"]>(`/api/v1/providers/${providerId}`, {
      method: "PATCH",
      body,
    });
  }

  deleteProvider(providerId: string) {
    return this.request<Schemas["ModelProviderOut"]>(`/api/v1/providers/${providerId}`, {
      method: "DELETE",
    });
  }

  syncProviderModels(providerId: string) {
    return this.request<Schemas["AvailableModelOut"][]>(`/api/v1/providers/${providerId}/sync-models`, {
      method: "POST",
    });
  }

  testProvider(providerId: string, body: Schemas["ProviderTestRequest"]) {
    return this.request<Schemas["ProviderTestOut"]>(`/api/v1/providers/${providerId}/test`, {
      method: "POST",
      body,
    });
  }

  setProviderCredential(providerId: string, body: Schemas["ProviderCredentialCreate"]) {
    return this.request<Schemas["ProviderCredentialOut"]>(`/api/v1/providers/${providerId}/credentials`, {
      method: "POST",
      body,
    });
  }

  getProviderCredential(providerId: string) {
    return this.request<Schemas["ProviderCredentialOut"]>(`/api/v1/providers/${providerId}/credentials`);
  }

  listModels() {
    return this.request<Schemas["AvailableModelOut"][]>("/api/v1/providers/models");
  }

  createModel(body: Schemas["AvailableModelCreate"]) {
    return this.request<Schemas["AvailableModelOut"]>("/api/v1/providers/models", { method: "POST", body });
  }

  updateModel(modelId: string, body: Schemas["AvailableModelUpdate"]) {
    return this.request<Schemas["AvailableModelOut"]>(`/api/v1/providers/models/${modelId}`, {
      method: "PATCH",
      body,
    });
  }

  listEmbeddingProviders() {
    return this.request<Schemas["EmbeddingProviderOut"][]>("/api/v1/providers/embedding-providers");
  }

  createEmbeddingProvider(body: Schemas["EmbeddingProviderCreate"]) {
    return this.request<Schemas["EmbeddingProviderOut"]>("/api/v1/providers/embedding-providers", {
      method: "POST",
      body,
    });
  }

  updateEmbeddingProvider(embeddingProviderId: string, body: Schemas["EmbeddingProviderUpdate"]) {
    return this.request<Schemas["EmbeddingProviderOut"]>(
      `/api/v1/providers/embedding-providers/${embeddingProviderId}`,
      { method: "PATCH", body },
    );
  }

  listTags() {
    return this.request<Schemas["TagOut"][]>("/api/v1/tags");
  }

  createTag(body: Schemas["TagCreate"]) {
    return this.request<Schemas["TagOut"]>("/api/v1/tags", { method: "POST", body });
  }

  updateTag(tagId: string, body: Schemas["TagUpdate"]) {
    return this.request<Schemas["TagOut"]>(`/api/v1/tags/${tagId}`, { method: "PATCH", body });
  }

  deleteTag(tagId: string) {
    return this.request<Schemas["TagOut"]>(`/api/v1/tags/${tagId}`, { method: "DELETE" });
  }

  getSystemSettings() {
    return this.request<Schemas["SystemSettingsOut"]>("/api/v1/settings");
  }

  updateSystemSettings(body: Schemas["SystemSettingsUpdate"]) {
    return this.request<Schemas["SystemSettingsOut"]>("/api/v1/settings", { method: "PUT", body });
  }

  listPromptTemplates() {
    return this.request<Schemas["PromptTemplateDetail"][]>("/api/v1/prompt-templates");
  }

  createPromptTemplate(templateType: string, body: Schemas["PromptTemplateUpsertRequest"]) {
    return this.request<Schemas["PromptTemplateOut"]>(`/api/v1/prompt-templates/${templateType}`, {
      method: "POST",
      body,
    });
  }

  updatePromptTemplate(templateType: string, body: Schemas["PromptTemplateUpsertRequest"]) {
    return this.request<Schemas["PromptTemplateOut"]>(`/api/v1/prompt-templates/${templateType}`, {
      method: "PUT",
      body,
    });
  }

  resetPromptTemplate(templateType: string) {
    return this.request<Schemas["PromptTemplateOut"]>(`/api/v1/prompt-templates/${templateType}/reset`, {
      method: "POST",
    });
  }

  listCocoons() {
    return this.request<Schemas["CocoonOut"][]>("/api/v1/cocoons");
  }

  createCocoon(body: Schemas["CocoonCreate"]) {
    return this.request<Schemas["CocoonOut"]>("/api/v1/cocoons", { method: "POST", body });
  }

  getCocoonTree() {
    return this.request<Schemas["CocoonTreeNode"][]>("/api/v1/cocoons/tree");
  }

  getCocoon(cocoonId: string) {
    return this.request<Schemas["CocoonOut"]>(`/api/v1/cocoons/${cocoonId}`);
  }

  updateCocoon(cocoonId: string, body: Schemas["CocoonUpdate"]) {
    return this.request<Schemas["CocoonOut"]>(`/api/v1/cocoons/${cocoonId}`, { method: "PATCH", body });
  }

  deleteCocoon(cocoonId: string) {
    return this.request<Schemas["CocoonOut"]>(`/api/v1/cocoons/${cocoonId}`, { method: "DELETE" });
  }

  getSessionState(cocoonId: string) {
    return this.request<Schemas["SessionStateOut"]>(`/api/v1/cocoons/${cocoonId}/state`);
  }

  listMessages(cocoonId: string) {
    return this.request<Schemas["ChatMessageOut"][]>(`/api/v1/cocoons/${cocoonId}/messages`);
  }

  listCocoonTags(cocoonId: string) {
    return this.request<Schemas["CocoonTagBindingOut"][]>(`/api/v1/cocoons/${cocoonId}/tags`);
  }

  bindCocoonTag(cocoonId: string, body: Schemas["CocoonTagBindRequest"]) {
    return this.request<Schemas["CocoonTagBindResult"]>(`/api/v1/cocoons/${cocoonId}/tags`, {
      method: "POST",
      body,
    });
  }

  unbindCocoonTag(cocoonId: string, tagId: string) {
    return this.request<Schemas["CocoonTagBindResult"]>(`/api/v1/cocoons/${cocoonId}/tags/${tagId}`, {
      method: "DELETE",
    });
  }

  sendMessage(cocoonId: string, body: Schemas["ChatMessageCreate"]) {
    return this.request<Schemas["AcceptedResponse"]>(`/api/v1/cocoons/${cocoonId}/messages`, {
      method: "POST",
      body,
    });
  }

  editUserMessage(cocoonId: string, body: Schemas["UserMessageEditRequest"]) {
    return this.request<Schemas["AcceptedResponse"]>(`/api/v1/cocoons/${cocoonId}/user_message`, {
      method: "PATCH",
      body,
    });
  }

  retryReply(cocoonId: string, body: Schemas["RetryReplyRequest"]) {
    return this.request<Schemas["AcceptedResponse"]>(`/api/v1/cocoons/${cocoonId}/reply/retry`, {
      method: "POST",
      body,
    });
  }

  requestRollback(cocoonId: string, body: Schemas["RollbackRequest"]) {
    return this.request<Schemas["DurableJobOut"]>(`/api/v1/cocoons/${cocoonId}/rollback`, {
      method: "POST",
      body,
    });
  }

  listMemory(cocoonId: string) {
    return this.request<Schemas["MemoryChunkOut"][]>(`/api/v1/memory/${cocoonId}`);
  }

  compactMemory(cocoonId: string, body: Schemas["MemoryCompactionRequest"]) {
    return this.request<Schemas["DurableJobOut"]>(`/api/v1/memory/${cocoonId}/compact`, {
      method: "POST",
      body,
    });
  }

  deleteMemory(cocoonId: string, memoryId: string) {
    return this.request<Schemas["MemoryChunkOut"]>(`/api/v1/memory/${cocoonId}/${memoryId}`, {
      method: "DELETE",
    });
  }

  listCheckpoints(cocoonId: string) {
    return this.request<Schemas["CheckpointOut"][]>(`/api/v1/checkpoints/${cocoonId}`);
  }

  createCheckpoint(body: Schemas["CheckpointCreate"]) {
    return this.request<Schemas["CheckpointOut"]>("/api/v1/checkpoints", { method: "POST", body });
  }

  listWakeupTasks() {
    return this.request<Schemas["WakeupTaskOut"][]>("/api/v1/wakeup");
  }

  enqueueWakeup(body: Schemas["WakeupRequest"]) {
    return this.request<Schemas["WakeupEnqueueResult"]>("/api/v1/wakeup", { method: "POST", body });
  }

  listPulls() {
    return this.request<Schemas["PullJobOut"][]>("/api/v1/pulls");
  }

  enqueuePull(body: Schemas["PullRequest"]) {
    return this.request<Schemas["PullEnqueueResult"]>("/api/v1/pulls", { method: "POST", body });
  }

  listMerges() {
    return this.request<Schemas["MergeJobOut"][]>("/api/v1/merges");
  }

  enqueueMerge(body: Schemas["MergeRequest"]) {
    return this.request<Schemas["MergeEnqueueResult"]>("/api/v1/merges", { method: "POST", body });
  }

  listAudits() {
    return this.request<Schemas["AuditRunOut"][]>("/api/v1/audits");
  }

  getAudit(runId: string) {
    return this.request<Schemas["AuditRunDetail"]>(`/api/v1/audits/${runId}`);
  }

  getInsights() {
    return this.request<Schemas["InsightsSummary"]>("/api/v1/insights/summary");
  }

  listArtifacts() {
    return this.request<Schemas["AuditArtifactOut"][]>("/api/v1/admin/artifacts");
  }

  cleanupExpiredArtifacts() {
    return this.request<Schemas["DurableJobOut"]>("/api/v1/admin/artifacts/cleanup", { method: "POST" });
  }

  cleanupArtifacts(body: Schemas["ArtifactCleanupRequest"]) {
    return this.request<Schemas["DurableJobOut"]>("/api/v1/admin/artifacts/cleanup/manual", {
      method: "POST",
      body,
    });
  }
}

function safeJson(raw: string): unknown {
  try {
    return JSON.parse(raw) as unknown;
  } catch {
    return raw;
  }
}

export function createCocoonApiClient(options: ApiClientOptions): CocoonApiClient {
  return new CocoonApiClient(options);
}
