import { ApiError, createCocoonApiClient, type CocoonApiClient } from "@cocoon-sit/ts-sdk";
import { toast } from "sonner";

import { useUserStore } from "@/store/useUserStore";

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
    toast.error("登录已失效，请重新登录");
    window.location.href = "/login";
  }
}

export function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    const data = error.data as
      | { code?: string; msg?: string; message?: string; detail?: string; data?: { errors?: Array<{ msg?: string }> } }
      | string
      | null;
    if (typeof data === "string") {
      return data;
    }
    const validationMessage = data?.data?.errors?.[0]?.msg;
    return data?.msg || data?.detail || data?.message || validationMessage || error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "请求失败";
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
  if (init?.body && !headers.has("Content-Type")) {
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
