import { ApiError, createCocoonApiClient, type CocoonApiClient } from "@cocoon-sit/ts-sdk";
import { toast } from "sonner";

import i18n from "@/i18n";
import { useUserStore } from "@/store/useUserStore";

const API_ERROR_KEY_BY_CODE: Record<string, string> = {
  AUTH_MISSING_BEARER: "common:apiErrors.authMissingBearer",
  AUTH_INVALID_CREDENTIALS: "common:apiErrors.authInvalidCredentials",
  AUTH_INVALID_REFRESH_TOKEN: "common:apiErrors.authInvalidRefreshToken",
  AUTH_UNKNOWN_REFRESH_TOKEN: "common:apiErrors.authUnknownRefreshToken",
  AUTH_INVALID_TOKEN: "common:apiErrors.authInvalidToken",
  AUTH_INACTIVE_USER: "common:apiErrors.authInactiveUser",
  AUTH_USER_INACTIVE: "common:apiErrors.authUserInactive",
  AUTH_REGISTRATION_UNAVAILABLE: "common:apiErrors.authRegistrationUnavailable",
  AUTH_REGISTRATION_DISABLED: "common:apiErrors.authRegistrationDisabled",
  INVITE_QUOTA_EXCEEDED: "common:apiErrors.inviteQuotaExceeded",
  VALIDATION_ERROR: "common:apiErrors.requestValidationFailed",
  INTERNAL_SERVER_ERROR: "common:apiErrors.internalServerError",
};

const API_ERROR_KEY_BY_MESSAGE: Record<string, string> = {
  "Missing bearer token": "common:apiErrors.authMissingBearer",
  "Invalid credentials": "common:apiErrors.authInvalidCredentials",
  "Invalid refresh token": "common:apiErrors.authInvalidRefreshToken",
  "Unknown refresh token": "common:apiErrors.authUnknownRefreshToken",
  "Invalid token": "common:apiErrors.authInvalidToken",
  "Inactive user": "common:apiErrors.authInactiveUser",
  "User account is inactive": "common:apiErrors.authUserInactive",
  "Registration is unavailable": "common:apiErrors.authRegistrationUnavailable",
  "Registration is disabled": "common:apiErrors.authRegistrationDisabled",
  "Username already exists": "common:apiErrors.usernameAlreadyExists",
  "Email already exists": "common:apiErrors.emailAlreadyExists",
  "Invite not found": "common:apiErrors.inviteNotFound",
  "Invite revoked": "common:apiErrors.inviteRevoked",
  "Invite expired": "common:apiErrors.inviteExpired",
  "Invite quota exceeded": "common:apiErrors.inviteQuotaExceeded",
  "Default user role is not configured": "common:apiErrors.defaultUserRoleMissing",
  "User not found": "common:apiErrors.userNotFound",
  "Role not found": "common:apiErrors.roleNotFound",
  "Registration group not found": "common:apiErrors.registrationGroupNotFound",
  "Only administrators can create permanent invites": "common:apiErrors.permanentInviteAdminOnly",
  "Group source_id is required": "common:apiErrors.inviteGroupSourceRequired",
  "Unsupported invite source": "common:apiErrors.unsupportedInviteSource",
  "Invite already revoked": "common:apiErrors.inviteAlreadyRevoked",
  "Used invites cannot be revoked": "common:apiErrors.usedInviteCannotBeRevoked",
  "Unsupported grant target": "common:apiErrors.unsupportedGrantTarget",
  "Only administrators can revoke invite grants": "common:apiErrors.inviteGrantAdminOnly",
  "Only administrators can update invite quota balances": "common:apiErrors.inviteQuotaBalanceAdminOnly",
  "Invite grant not found": "common:apiErrors.inviteGrantNotFound",
  "Invite grant already revoked": "common:apiErrors.inviteGrantAlreadyRevoked",
  "Unsupported summary target": "common:apiErrors.unsupportedSummaryTarget",
  "Group not found": "common:apiErrors.groupNotFound",
  "Root group cannot have a parent": "common:apiErrors.rootGroupCannotHaveParent",
  "Group cannot be its own parent": "common:apiErrors.groupCannotBeOwnParent",
  "Root group cannot be deleted": "common:apiErrors.rootGroupCannotBeDeleted",
  "Group member not found": "common:apiErrors.groupMemberNotFound",
  "Group parent would create a cycle": "common:apiErrors.groupParentCycle",
  "Users cannot change their own role, permissions, or active status": "common:apiErrors.usersCannotEditSelf",
  "Bootstrap admin role, permissions, and active status are managed by configuration": "common:apiErrors.bootstrapAdminManaged",
  "Character not found": "common:apiErrors.characterNotFound",
  "Character access denied": "common:apiErrors.characterAccessDenied",
  "Character is still used by an existing cocoon": "common:apiErrors.characterInUse",
  "Character ACL not found": "common:apiErrors.characterAclNotFound",
  "Cocoon not found": "common:apiErrors.cocoonNotFound",
  "Cocoon access denied": "common:apiErrors.cocoonAccessDenied",
  "Chat group room not found": "common:apiErrors.chatGroupRoomNotFound",
  "Chat group owner access denied": "common:apiErrors.chatGroupOwnerAccessDenied",
  "Chat group management denied": "common:apiErrors.chatGroupManagementDenied",
  "Chat group chat access denied": "common:apiErrors.chatGroupChatDenied",
  "Chat group access denied": "common:apiErrors.chatGroupAccessDenied",
  "Room owner role cannot be changed": "common:apiErrors.roomOwnerRoleCannotBeChanged",
  "Chat group member not found": "common:apiErrors.chatGroupMemberNotFound",
  "Room owner cannot be removed": "common:apiErrors.roomOwnerCannotBeRemoved",
  "Cannot retract this message": "common:apiErrors.cannotRetractMessage",
  "Cannot retract AI message": "common:apiErrors.cannotRetractAiMessage",
  "Message not found": "common:apiErrors.messageNotFound",
  "User message not found": "common:apiErrors.userMessageNotFound",
  "Memory not found": "common:apiErrors.memoryNotFound",
  "Session state not found": "common:apiErrors.sessionStateNotFound",
  "Anchor message not found": "common:apiErrors.anchorMessageNotFound",
  "A root cocoon already exists for this user and character": "common:apiErrors.rootCocoonAlreadyExists",
  "System tag cannot be unbound": "common:apiErrors.systemTagCannotBeUnbound",
  "Tag binding not found": "common:apiErrors.tagBindingNotFound",
  "System tag cannot be modified": "common:apiErrors.systemTagCannotBeModified",
  "Tag not found": "common:apiErrors.tagNotFound",
  "System tag cannot be deleted": "common:apiErrors.systemTagCannotBeDeleted",
  "Provider not found": "common:apiErrors.providerNotFound",
  "Provider is still referenced by existing cocoons": "common:apiErrors.providerInUseByCocoons",
  "Provider is still referenced by an embedding provider": "common:apiErrors.providerInUseByEmbedding",
  "Model not found for provider": "common:apiErrors.modelNotFoundForProvider",
  "Provider base_url is required": "common:apiErrors.providerBaseUrlRequired",
  "Provider credential not found": "common:apiErrors.providerCredentialNotFound",
  "Provider returned no models": "common:apiErrors.providerReturnedNoModels",
  "Model not found": "common:apiErrors.modelNotFound",
  "Embedding provider not found": "common:apiErrors.embeddingProviderNotFound",
  "Template not found": "common:apiErrors.templateNotFound",
  "No active revision": "common:apiErrors.noActiveRevision",
  "Request validation failed": "common:apiErrors.requestValidationFailed",
  "Internal server error": "common:apiErrors.internalServerError",
  "Audit run not found": "common:apiErrors.auditRunNotFound",
  "Audit run access denied": "common:apiErrors.auditRunAccessDenied",
  "Plugin not found": "common:apiErrors.pluginNotFound",
  "Failed to generate unique invite code": "common:apiErrors.inviteCodeGenerationFailed",
  "Selected model is not allowed by system settings": "common:apiErrors.selectedModelNotAllowed",
};

const API_ERROR_PATTERNS: Array<{
  pattern: RegExp;
  translate: (match: RegExpMatchArray) => string;
}> = [
  {
    pattern: /^Missing permission: (.+)$/,
    translate: (match) => i18n.t("common:apiErrors.missingPermission", { permission: match[1] }),
  },
  {
    pattern: /^Unsupported tag visibility: (.+)$/,
    translate: (match) => i18n.t("common:apiErrors.unsupportedTagVisibility", { value: match[1] }),
  },
  {
    pattern: /^Chat group not found: (.+)$/,
    translate: (match) => i18n.t("common:apiErrors.chatGroupNotFound", { id: match[1] }),
  },
  {
    pattern: /^Unknown allowed model ids: (.+)$/,
    translate: (match) => i18n.t("common:apiErrors.unknownAllowedModelIds", { ids: match[1] }),
  },
  {
    pattern: /^Model sync is not supported for provider kind: (.+)$/,
    translate: (match) => i18n.t("common:apiErrors.providerSyncUnsupported", { kind: match[1] }),
  },
  {
    pattern: /^Failed to sync provider models: (.+)$/,
    translate: (match) => i18n.t("common:apiErrors.providerSyncFailed", { reason: match[1] }),
  },
  {
    pattern: /^Unknown prompt variables: (.+)$/,
    translate: (match) => i18n.t("common:apiErrors.unknownPromptVariables", { variables: match[1] }),
  },
  {
    pattern: /^Missing prompt variables: (.+)$/,
    translate: (match) => i18n.t("common:apiErrors.missingPromptVariables", { variables: match[1] }),
  },
];

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, "");
}

function stripApiPrefix(value: string) {
  return value.replace(/\/api\/v1\/?$/, "");
}

export function getApiBaseUrl() {
  const explicit = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (explicit) {
    return stripApiPrefix(trimTrailingSlash(explicit));
  }

  if (typeof window !== "undefined") {
    return stripApiPrefix(trimTrailingSlash(window.location.origin));
  }

  return "http://127.0.0.1:8000";
}

function normalizeApiPath(path: string) {
  return path.startsWith("/") ? path : `/${path}`;
}

function handleUnauthorized() {
  useUserStore.getState().logout();
  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    toast.error(i18n.t("common:sessionExpired"));
    window.location.href = "/login";
  }
}

export function localizeApiMessage(message: string, code?: string | null) {
  if (!message) {
    return message;
  }

  if (code) {
    const codeKey = API_ERROR_KEY_BY_CODE[code];
    if (codeKey) {
      return i18n.t(codeKey);
    }
  }

  const exactKey = API_ERROR_KEY_BY_MESSAGE[message];
  if (exactKey) {
    return i18n.t(exactKey);
  }

  for (const entry of API_ERROR_PATTERNS) {
    const match = message.match(entry.pattern);
    if (match) {
      return entry.translate(match);
    }
  }

  return message;
}

export function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    const data = error.data as
      | { code?: string; msg?: string; message?: string; detail?: string; data?: { errors?: Array<{ msg?: string }> } }
      | string
      | null;
    if (typeof data === "string") {
      return localizeApiMessage(data);
    }
    const validationMessage = data?.data?.errors?.[0]?.msg;
    const resolved = data?.msg || data?.detail || data?.message || validationMessage || error.message;
    return localizeApiMessage(resolved, data?.code);
  }

  if (error instanceof Error) {
    return localizeApiMessage(error.message);
  }

  return i18n.t("common:requestFailed");
}

export function createAnonymousClient() {
  return createCocoonApiClient({ baseUrl: getApiBaseUrl() });
}

export function createTokenClient(accessToken: string) {
  return createCocoonApiClient({
    baseUrl: getApiBaseUrl(),
    getAccessToken: () => accessToken,
  });
}

export function getApiClient() {
  return createCocoonApiClient({
    baseUrl: getApiBaseUrl(),
    getAccessToken: () => useUserStore.getState().getToken(),
    onUnauthorized: handleUnauthorized,
  });
}

export function makeCocoonWsUrl(cocoonId: string) {
  return getApiClient().makeCocoonWsUrl(cocoonId);
}

export function makeChatGroupWsUrl(roomId: string) {
  return getApiClient().makeChatGroupWsUrl(roomId);
}

export function unsupportedFeature(message: string): never {
  throw new Error(message);
}

export function showErrorToast(error: unknown, fallback?: string) {
  const message = getErrorMessage(error);
  toast.error(message && !message.startsWith("Request failed with status") ? message : fallback || message);
}

export async function apiCall<T>(callback: (client: CocoonApiClient) => Promise<T>): Promise<T> {
  return callback(getApiClient());
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const accessToken = useUserStore.getState().getToken();
  const headers = new Headers(init?.headers || {});
  headers.set("Accept", "application/json");
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${getApiBaseUrl()}/api/v1${normalizeApiPath(path)}`, {
    ...init,
    headers,
  });

  const rawText = await response.text();
  let payload: unknown = null;
  if (rawText) {
    try {
      payload = JSON.parse(rawText);
    } catch {
      payload = rawText;
    }
  }

  if (response.status === 401) {
    handleUnauthorized();
  }

  if (!response.ok) {
    throw new Error(getErrorMessage(new ApiError(response.status, payload)));
  }

  if (
    payload &&
    typeof payload === "object" &&
    "data" in payload &&
    "code" in payload &&
    "msg" in payload
  ) {
    return (payload as { data: T }).data;
  }

  return payload as T;
}
