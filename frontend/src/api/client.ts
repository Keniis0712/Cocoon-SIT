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

function handleUnauthorized() {
  useUserStore.getState().logout();
  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    toast.error("登录已失效，请重新登录");
    window.location.href = "/login";
  }
}

export function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    const data = error.data as { detail?: string; message?: string } | string | null;
    if (typeof data === "string") {
      return data;
    }
    return data?.detail || data?.message || error.message;
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

export function unsupportedFeature(message: string): never {
  throw new Error(message);
}

export async function apiCall<T>(callback: (client: CocoonApiClient) => Promise<T>): Promise<T> {
  try {
    return await callback(getApiClient());
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 401)) {
      toast.error(`错误: ${getErrorMessage(error)}`);
    }
    throw error;
  }
}
