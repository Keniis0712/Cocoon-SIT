import { apiCall } from "./client";
import { rememberLegacyId, resolveActualId } from "./id-map";
import type {
  AvailableModelRead,
  ModelProviderPayload,
  ModelProviderRead,
  ModelProviderTestResponse,
  PageResp,
} from "./types";

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

function mapModel(item: { id: string; provider_id: string; model_name: string; created_at: string }): AvailableModelRead {
  return {
    id: rememberLegacyId("model", item.id),
    provider_id: rememberLegacyId("provider", item.provider_id),
    model_name: item.model_name,
    created_at: item.created_at,
    updated_at: item.created_at,
  };
}

async function loadProviderGraph() {
  const [providers, models] = await Promise.all([
    apiCall((client) => client.listProviders()),
    apiCall((client) => client.listModels()),
  ]);

  const modelMap = new Map<string, AvailableModelRead[]>();
  for (const model of models) {
    const mapped = mapModel(model);
    const bucket = modelMap.get(model.provider_id) || [];
    bucket.push(mapped);
    modelMap.set(model.provider_id, bucket);
  }

  return providers.map((provider) => ({
    id: rememberLegacyId("provider", provider.id),
    name: provider.name,
    base_url: provider.base_url || "",
    is_enabled: provider.is_enabled,
    created_at: provider.created_at,
    updated_at: provider.created_at,
    available_models: modelMap.get(provider.id) || [],
  } satisfies ModelProviderRead));
}

export function listModelProviders(page: number, page_size: number): Promise<PageResp<ModelProviderRead>> {
  return loadProviderGraph().then((items) => makePage(items, page, page_size));
}

export function createModelProvider(data: ModelProviderPayload): Promise<ModelProviderRead> {
  return apiCall(async (client) => {
    const created = await client.createProvider({
      name: data.name.trim(),
      kind: "openai_compatible",
      base_url: data.base_url.trim() || null,
      capabilities_json: {},
    });
    if (data.api_key.trim()) {
      await client.setProviderCredential(created.id, {
        secret: data.api_key.trim(),
        metadata_json: {},
      });
    }
    const items = await loadProviderGraph();
    return items.find((item) => item.id === rememberLegacyId("provider", created.id))!;
  });
}

export function updateModelProvider(id: number, data: Partial<ModelProviderPayload>): Promise<ModelProviderRead> {
  return apiCall(async (client) => {
    const updated = await client.updateProvider(resolveActualId("provider", id), {
      name: data.name?.trim() || "provider",
      kind: "openai_compatible",
      base_url: data.base_url?.trim() || null,
      capabilities_json: {},
    });
    if (data.api_key?.trim()) {
      await client.setProviderCredential(updated.id, {
        secret: data.api_key.trim(),
        metadata_json: {},
      });
    }
    const items = await loadProviderGraph();
    return items.find((item) => item.id === rememberLegacyId("provider", updated.id))!;
  });
}

export function syncModelProvider(_id: number): Promise<ModelProviderRead> {
  return apiCall(async (client) => {
    await client.syncProviderModels(resolveActualId("provider", _id));
    const items = await loadProviderGraph();
    const matched = items.find((item) => item.id === _id);
    if (!matched) {
      throw new Error("Provider not found after sync");
    }
    return matched;
  });
}

export function testModelProvider(
  _id: number,
  _payload: { selected_model_id: number; prompt: string },
): Promise<ModelProviderTestResponse> {
  return apiCall(async (client) => {
    const result = await client.testProvider(resolveActualId("provider", _id), {
      selected_model_id: resolveActualId("model", _payload.selected_model_id),
      prompt: _payload.prompt,
    });
    return {
      provider_id: rememberLegacyId("provider", result.provider_id),
      selected_model_id: rememberLegacyId("model", result.selected_model_id),
      model_name: result.model_name,
      reply: result.reply,
      structured_tests: [],
    };
  });
}

export function deleteModelProvider(_id: number) {
  return apiCall(async (client) => {
    await client.deleteProvider(resolveActualId("provider", _id));
  });
}
