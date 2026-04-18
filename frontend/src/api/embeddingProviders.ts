import { apiCall } from "./client";
import { rememberLegacyId, resolveActualId } from "./id-map";
import type { EmbeddingProviderPayload, EmbeddingProviderRead, PageResp } from "./types";

function makePage<T>(items: T[], page: number, pageSize: number): PageResp<T> {
  const total = items.length;
  const total_pages = Math.max(1, Math.ceil(total / pageSize));
  const start = Math.max(0, (page - 1) * pageSize);
  return {
    items: items.slice(start, start + pageSize),
    total,
    page,
    page_size: pageSize,
    total_pages,
  };
}

function mapEmbeddingProvider(item: {
  id: string;
  name: string;
  kind: string;
  provider_id: string | null;
  model_name: string;
  config_json: Record<string, unknown>;
  is_enabled: boolean;
  created_at: string;
}): EmbeddingProviderRead {
  return {
    id: rememberLegacyId("embedding-provider", item.id),
    name: item.name,
    kind: item.kind || (item.provider_id ? "openai_compatible" : "local_cpu"),
    base_url: typeof item.config_json.base_url === "string" ? item.config_json.base_url : null,
    model_name: item.kind === "openai_compatible" ? item.model_name : null,
    local_model_name: item.kind === "openai_compatible" ? null : item.model_name,
    device: typeof item.config_json.device === "string" ? item.config_json.device : "cpu",
    is_enabled: item.is_enabled,
    is_default: Boolean(item.config_json.is_default),
    created_at: item.created_at,
    updated_at: item.created_at,
  };
}

export function listEmbeddingProviders(page = 1, page_size = 100) {
  return apiCall(async (client) => {
    const items = (await client.listEmbeddingProviders()).map(mapEmbeddingProvider);
    return makePage(items, page, page_size);
  });
}

export function createEmbeddingProvider(payload: EmbeddingProviderPayload) {
  return apiCall(async (client) => {
    const created = await client.createEmbeddingProvider({
      name: payload.name.trim(),
      kind: payload.kind,
      provider_id: null,
      model_name:
        payload.kind === "openai_compatible"
          ? payload.model_name?.trim() || ""
          : payload.local_model_name?.trim() || payload.model_name?.trim() || "",
      config_json: {
        base_url: payload.base_url || null,
        device: payload.device || "cpu",
        is_default: payload.is_default ?? false,
      },
      api_key: payload.api_key?.trim() || null,
      is_enabled: payload.is_enabled ?? true,
    });
    return mapEmbeddingProvider(created);
  });
}

export function updateEmbeddingProvider(providerId: number, payload: Partial<EmbeddingProviderPayload>) {
  return apiCall(async (client) => {
    const updated = await client.updateEmbeddingProvider(resolveActualId("embedding-provider", providerId), {
      name: payload.name?.trim(),
      kind: payload.kind,
      provider_id: null,
      model_name:
        payload.kind === "openai_compatible"
          ? payload.model_name?.trim()
          : payload.local_model_name?.trim() || payload.model_name?.trim(),
      config_json: {
        base_url: payload.base_url || null,
        device: payload.device || "cpu",
        is_default: payload.is_default ?? false,
      },
      api_key: payload.api_key?.trim() || null,
      is_enabled: payload.is_enabled ?? true,
    });
    return mapEmbeddingProvider(updated);
  });
}
