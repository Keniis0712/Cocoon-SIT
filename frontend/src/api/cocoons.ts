import { apiCall, apiJson, makeCocoonWsUrl } from "./client";
import { createPendingUserMessage, mapWorkspaceMessage } from "./adapters/messages";
import { mapRuntimeWsEvent } from "./adapters/runtimeWs";
import {
  rememberLegacyId,
  rememberLegacyStringId,
  resolveActualId,
} from "./id-map";
import type {
  AvailableModelRead,
  CharacterRead,
  CocoonCompactionPayload,
  CocoonPayload,
  CocoonRead,
  CocoonTreeNode,
  CocoonTreeResponse,
  DurableJobRead,
  MemoryChunkRead,
  PageResp,
  TagRead,
} from "./types";
import type { ChatEnqueueResponse, ChatMessagePage, ChatRequest, ChatStreamEvent, RuntimeWsEvent } from "./types/chat";

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

function epochSecondsToIso(value: number | null | undefined) {
  if (typeof value !== "number") {
    return null;
  }
  return new Date(value * 1000).toISOString();
}

function mapCharacter(item: {
  id: string;
  name: string;
  prompt_summary: string;
  settings_json: Record<string, unknown>;
  created_by_user_id: string | null;
  created_at: string;
}): CharacterRead {
  const settings = item.settings_json || {};
  return {
    id: rememberLegacyId("character", item.id),
    name: item.name,
    owner_uid: item.created_by_user_id ? rememberLegacyStringId("user", item.created_by_user_id) : null,
    visibility: settings.visibility === "public" ? "public" : "private",
    description: typeof settings.description === "string" ? settings.description : null,
    personality_prompt:
      typeof settings.personality_prompt === "string" ? settings.personality_prompt : item.prompt_summary,
    created_at: item.created_at,
  };
}

function mapTag(item: {
  id: string;
  tag_id: string;
  brief: string;
  visibility: string;
  is_system?: boolean;
  visible_chat_group_ids?: string[];
  created_at: string;
}): TagRead {
  return {
    id: rememberLegacyId("tag", item.id),
    actual_id: item.id,
    tag_id: item.tag_id,
    name: item.tag_id,
    brief: item.brief,
    visibility_mode: item.visibility || "private",
    is_system: Boolean(item.is_system),
    visible_chat_group_ids: item.visible_chat_group_ids ?? [],
    created_at: item.created_at,
    updated_at: item.created_at,
  };
}

function mapModel(item: {
  id: string;
  provider_id: string;
  model_name: string;
  created_at: string;
}): AvailableModelRead {
  return {
    id: rememberLegacyId("model", item.id),
    provider_id: rememberLegacyId("provider", item.provider_id),
    model_name: item.model_name,
    created_at: item.created_at,
    updated_at: item.created_at,
  };
}

async function loadReferences() {
  const [characters, providers, models, tags] = await Promise.all([
    apiCall((client) => client.listCharacters()),
    apiCall((client) => client.listProviders()),
    apiCall((client) => client.listModels()),
    apiCall((client) => client.listTags()),
  ]);

  const mappedCharacters = new Map(characters.map((item) => [item.id, mapCharacter(item)] as const));
  const mappedTags = new Map(tags.map((item) => [item.id, mapTag(item)] as const));
  const mappedModels = new Map(models.map((item) => [item.id, mapModel(item)] as const));

  const mappedProviders = providers.map((provider) => ({
    id: rememberLegacyId("provider", provider.id),
    name: provider.name,
    base_url: provider.base_url || "",
    is_enabled: provider.is_enabled,
    created_at: provider.created_at,
    updated_at: provider.created_at,
    available_models: models.filter((item) => item.provider_id === provider.id).map(mapModel),
  }));
  const providerMap = new Map(mappedProviders.map((item) => [item.id, item] as const));

  return { mappedCharacters, mappedTags, mappedModels, providerMap };
}

async function mapCocoon(item: {
  id: string;
  name: string;
  owner_user_id: string;
  character_id: string;
  selected_model_id: string;
  default_temperature?: number;
  max_context_messages?: number;
  auto_compaction_enabled?: boolean;
  memory_profile?: string;
  parent_id: string | null;
  created_at: string;
}, boundTagIds: string[] = []): Promise<CocoonRead> {
  const refs = await loadReferences();
  const selectedModel = refs.mappedModels.get(item.selected_model_id) || null;
  const provider = selectedModel ? refs.providerMap.get(selectedModel.provider_id) || null : null;
  const tags = boundTagIds.map((tagId) => refs.mappedTags.get(tagId)).filter(Boolean) as TagRead[];

  return {
    id: rememberLegacyId("cocoon", item.id),
    name: item.name,
    owner_uid: rememberLegacyStringId("user", item.owner_user_id),
    default_temperature: item.default_temperature ?? null,
    max_context_messages: item.max_context_messages ?? null,
    auto_compaction_enabled: item.auto_compaction_enabled ?? null,
    memory_profile: item.memory_profile ?? "meta_reply",
    kind: "private",
    chat_group_id: null,
    parent_id: item.parent_id ? rememberLegacyId("cocoon", item.parent_id) : null,
    last_read_msg_id: null,
    debounce_until: null,
    dispatch_status: "idle",
    sync_mode: "branch",
    fork_anchor_msg_id: null,
    fork_at_msg_id: null,
    fork_at_ts: null,
    active_checkpoint_id: null,
    rollback_activated_at: null,
    context_prompt: null,
    max_context_tokens: item.max_context_messages ?? null,
    max_rounds: null,
    compact_memory_max_items: 0,
    auto_compaction_trigger_rounds: 0,
    auto_compaction_message_count: 0,
    auto_compaction_memory_max_items: 0,
    manual_compaction_message_count: 0,
    manual_compaction_memory_max_items: 0,
    manual_compaction_mode: "all",
    character_id: rememberLegacyId("character", item.character_id),
    provider_id: provider?.id || 0,
    selected_model_id: selectedModel?.id || rememberLegacyId("model", item.selected_model_id),
    created_at: item.created_at,
    character: refs.mappedCharacters.get(item.character_id) || null,
    provider: provider || null,
    selected_model: selectedModel,
    tags,
    dispatch_job: null,
  };
}

function mapTreeNode(item: { id: string; name: string; parent_id: string | null; children?: any[] }): CocoonTreeNode {
  return {
    id: rememberLegacyId("cocoon", item.id),
    name: item.name,
    owner_uid: null,
    kind: "private",
    chat_group_id: null,
    parent_id: item.parent_id ? rememberLegacyId("cocoon", item.parent_id) : null,
    last_read_msg_id: null,
    debounce_until: null,
    dispatch_status: "idle",
    sync_mode: "branch",
    fork_anchor_msg_id: null,
    fork_at_msg_id: null,
    fork_at_ts: null,
    active_checkpoint_id: null,
    rollback_activated_at: null,
    context_prompt: null,
    max_context_tokens: null,
    max_rounds: null,
    compact_memory_max_items: 0,
    auto_compaction_trigger_rounds: 0,
    auto_compaction_message_count: 0,
    auto_compaction_memory_max_items: 0,
    manual_compaction_message_count: 0,
    manual_compaction_memory_max_items: 0,
    manual_compaction_mode: "all",
    character_id: 0,
    provider_id: 0,
    selected_model_id: 0,
    created_at: "",
    has_children: Boolean(item.children?.length),
    children: (item.children || []).map((child) => mapTreeNode(child as { id: string; name: string; parent_id: string | null; children?: any[] })),
  };
}

function mapMemory(item: {
  id: string;
  cocoon_id?: string | null;
  chat_group_id?: string | null;
  owner_user_id?: string | null;
  memory_pool?: string;
  memory_type?: string;
  importance?: number;
  confidence?: number;
  status?: string;
  valid_until?: string | null;
  last_accessed_at?: string | null;
  access_count?: number;
  meta_json?: Record<string, unknown>;
  source_message_id?: string | null;
  scope: string;
  content: string;
  summary: string | null;
  tags_json: string[];
  source_kind?: string;
  created_at: string;
}): MemoryChunkRead {
  return {
    id: rememberLegacyId("memory", item.id),
    cocoon_id: item.cocoon_id ? rememberLegacyId("cocoon", item.cocoon_id) : null,
    chat_group_id: item.chat_group_id ? rememberLegacyId("group", item.chat_group_id) : null,
    owner_user_id: item.owner_user_id ?? null,
    memory_pool: item.memory_pool ?? "tree_private",
    memory_type: item.memory_type ?? "summary",
    status: item.status ?? "active",
    summary: item.summary,
    valid_until: item.valid_until ?? null,
    last_accessed_at: item.last_accessed_at ?? null,
    access_count: item.access_count ?? 0,
    meta_json: item.meta_json ?? {},
    origin_cocoon_id: null,
    source_message_id: item.source_message_id ? rememberLegacyId("message", item.source_message_id) : null,
    chroma_document_id: item.id,
    role_key: item.scope,
    source_kind: item.source_kind ?? item.scope,
    content: item.content,
    visibility: 0,
    importance: item.importance ?? 0,
    confidence: item.confidence ?? 3,
    timestamp: new Date(item.created_at).getTime(),
    is_thought: false,
    is_summary: Boolean(item.summary),
    created_at: item.created_at,
    source_message: null,
    tags: item.tags_json,
  };
}

export function getCocoons(page: number, page_size: number, _scope: "mine" | "all" = "mine"): Promise<PageResp<CocoonRead>> {
  return apiCall(async (client) => {
    const items = await Promise.all((await client.listCocoons()).map((item) => mapCocoon(item)));
    return makePage(items, page, page_size);
  });
}

export function getCocoonTree(
  page: number,
  page_size: number,
  _max_depth: number,
  parent_id?: number | "",
  _scope: "mine" | "all" = "mine",
): Promise<CocoonTreeResponse> {
  return apiCall(async (client) => {
    const roots = (await client.getCocoonTree()).map(mapTreeNode);
    const parentNumeric = typeof parent_id === "number" ? parent_id : null;
    const items = parentNumeric ? roots.find((item) => item.id === parentNumeric)?.children || [] : roots;
    const paged = makePage(items, page, page_size);
    return {
      ...paged,
      parent_id: parentNumeric,
      max_depth: 2,
    };
  });
}

export function getCocoon(id: number): Promise<CocoonRead> {
  return apiCall(async (client) => {
    const actualId = resolveActualId("cocoon", id);
    const [cocoon, tags] = await Promise.all([
      client.getCocoon(actualId),
      client.listCocoonTags(actualId),
    ]);
    return mapCocoon(cocoon, tags.map((item) => item.tag_id));
  });
}

export function getCocoonSessionState(cocoonId: number) {
  return apiCall(async (client) => {
    const state = await client.getSessionState(resolveActualId("cocoon", cocoonId));
    return {
      relation_score: state.relation_score,
      persona_json: state.persona_json || {},
      active_tags: state.active_tags_json || [],
      current_model_id: null,
      current_wakeup_task_id: state.current_wakeup_task_id ?? null,
      dispatch_status: null as string | null,
      debounce_until: null as string | null,
    };
  });
}

export function createCocoon(data: CocoonPayload): Promise<CocoonRead> {
  return apiCall(async (client) => {
    const payload: any = {
      name: data.name.trim(),
      parent_id: data.parent_id ? resolveActualId("cocoon", data.parent_id) : null,
      default_temperature: data.default_temperature ?? 0.7,
      max_context_messages: data.max_context_messages ?? data.max_context_tokens ?? 12,
      memory_profile: data.memory_profile ?? undefined,
    };
    if (data.character_id) {
      payload.character_id = resolveActualId("character", data.character_id);
    }
    if (data.selected_model_id) {
      payload.selected_model_id = resolveActualId("model", data.selected_model_id);
    }
    const created = await client.createCocoon(payload);
    return getCocoon(rememberLegacyId("cocoon", created.id));
  });
}

export function updateCocoon(id: number, data: Partial<CocoonPayload>): Promise<CocoonRead> {
  return apiCall(async (client) => {
    const updated = await client.updateCocoon(resolveActualId("cocoon", id), {
      name: data.name?.trim(),
      character_id: data.character_id ? resolveActualId("character", data.character_id) : undefined,
      selected_model_id: data.selected_model_id ? resolveActualId("model", data.selected_model_id) : undefined,
      max_context_messages: data.max_context_messages ?? data.max_context_tokens ?? undefined,
      auto_compaction_enabled: data.auto_compaction_enabled ?? undefined,
      default_temperature: data.default_temperature ?? undefined,
      memory_profile: data.memory_profile ?? undefined,
    } as any);
    return getCocoon(rememberLegacyId("cocoon", updated.id));
  });
}

export function deleteCocoon(_id: number) {
  return apiCall(async (client) => {
    return mapCocoon(await client.deleteCocoon(resolveActualId("cocoon", _id)));
  });
}

export function getCocoonMessages(
  cocoon_id: number,
  before_message_id: number | null,
  page_size: number,
): Promise<ChatMessagePage> {
  return apiCall(async (client) => {
    const actualCocoonId = resolveActualId("cocoon", cocoon_id);
    const beforeActual = before_message_id ? resolveActualId("message", before_message_id) : null;
    const rawItems = await client.listMessages(actualCocoonId, {
      beforeMessageId: beforeActual,
      limit: page_size + 1,
    });
    const hasMore = rawItems.length > page_size;
    const pageItems = hasMore ? rawItems.slice(1) : rawItems;
    const items = pageItems.map(mapWorkspaceMessage);
    return {
      items,
      total: items.length + (hasMore ? 1 : 0),
      page: 1,
      page_size,
      total_pages: 1,
      has_more: hasMore,
    };
  });
}

export function getCocoonMemories(cocoon_id: number): Promise<{ items: MemoryChunkRead[]; overview: any }> {
  return apiJson(`/memory/${resolveActualId("cocoon", cocoon_id)}`).then((payload: any) => ({
    items: Array.isArray(payload.items) ? payload.items.map((item: any) => mapMemory(item)) : [],
    overview: payload.overview ?? {
      total: 0,
      by_pool: {},
      by_type: {},
      by_status: {},
      tag_cloud: [],
      importance_average: 0,
      confidence_average: 0,
    },
  }));
}

export function updateCocoonMemory(
  cocoon_id: number,
  memory_id: number,
  data: {
    content?: string;
    summary?: string | null;
    tags_json?: string[];
    importance?: number;
    confidence?: number;
    status?: string;
  },
) {
  return apiJson(
    `/memory/${resolveActualId("cocoon", cocoon_id)}/${resolveActualId("memory", memory_id)}`,
    {
      method: "PATCH",
      body: JSON.stringify(data),
    },
  ).then((item: any) => mapMemory(item));
}

export function reorganizeCocoonMemories(
  cocoon_id: number,
  data: { memory_ids: number[]; instructions?: string },
) {
  return apiJson(`/memory/${resolveActualId("cocoon", cocoon_id)}/reorganize`, {
    method: "POST",
    body: JSON.stringify({
      memory_ids: data.memory_ids.map((id) => resolveActualId("memory", id)),
      instructions: data.instructions ?? null,
    }),
  });
}

export function deleteCocoonMemory(_cocoon_id: number, _memory_id: number) {
  return apiCall(async (client) => {
    return mapMemory(
      await client.deleteMemory(resolveActualId("cocoon", _cocoon_id), resolveActualId("memory", _memory_id)),
    );
  });
}

export function compactCocoonContext(cocoon_id: number, _data: CocoonCompactionPayload): Promise<DurableJobRead> {
  return apiCall(async (client) => {
    return client.compactMemory(resolveActualId("cocoon", cocoon_id), {
      before_message_id: null,
    });
  });
}

export function deleteCocoonReply(_cocoon_id: number) {
  throw new Error("Deleting replies is not supported by the current backend");
}

export function sendCocoonMessage(cocoon_id: number, data: ChatRequest) {
  return apiCall(async (client) => {
    const accepted = await client.sendMessage(resolveActualId("cocoon", cocoon_id), {
      content: data.content,
      client_request_id: data.client_request_id || `${Date.now()}`,
      timezone: data.timezone ?? null,
    });
    return {
      accepted: accepted.accepted,
      dispatch_status: accepted.status,
      debounce_until: epochSecondsToIso(accepted.debounce_until),
      user_message: createPendingUserMessage(accepted.action_id, data.content, {
        kind: "cocoon",
        targetId: cocoon_id,
      }),
    } satisfies ChatEnqueueResponse;
  });
}

export function connectCocoonWorkspaceSocket(
  cocoonId: number,
  handlers: {
      onMessage: (event: RuntimeWsEvent) => void;
      onOpen?: () => void;
      onClose?: (event: CloseEvent) => void;
      onError?: (event: Event) => void;
  },
) {
  const socket = new WebSocket(makeCocoonWsUrl(resolveActualId("cocoon", cocoonId)));
  socket.onopen = () => {
    handlers.onOpen?.();
  };
  socket.onmessage = (event) => {
    handlers.onMessage(
      mapRuntimeWsEvent(JSON.parse(String(event.data)), mapWorkspaceMessage, {
        mapModelId: (modelId) => (modelId ? rememberLegacyId("model", String(modelId)) : null),
      }),
    );
  };
  socket.onerror = (event) => handlers.onError?.(event);
  socket.onclose = (event) => handlers.onClose?.(event);
  return socket;
}

export function updateCocoonUserMessage(
  _cocoon_id: number,
  _data: { message_id: number; content: string },
  _onEvent: (event: ChatStreamEvent) => void,
) {
  return apiCall(async (client) => {
    const accepted = await client.editUserMessage(resolveActualId("cocoon", _cocoon_id), {
      message_id: resolveActualId("message", _data.message_id),
      content: _data.content,
    });
    return accepted;
  });
}

export function retryCocoonReply(
  cocoon_id: number,
  _onEvent: (event: ChatStreamEvent) => void,
) {
  return apiCall((client) => client.retryReply(resolveActualId("cocoon", cocoon_id), { message_id: null }));
}
