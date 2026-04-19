import { apiCall, makeCocoonWsUrl } from "./client";
import {
  rememberLegacyId,
  rememberLegacyStringId,
  resolveActualId,
} from "./id-map";
import type {
  AvailableModelRead,
  CharacterRead,
  ChatEnqueueResponse,
  ChatMessagePage,
  ChatRequest,
  ChatStreamEvent,
  CocoonCompactionPayload,
  CocoonPayload,
  CocoonRead,
  CocoonTreeNode,
  CocoonTreeResponse,
  DurableJobRead,
  MemoryChunkRead,
  PageResp,
  RuntimeWsEvent,
  StatePatchEvent,
  TagRead,
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
  is_isolated: boolean;
  meta_json: Record<string, unknown>;
  created_at: string;
}): TagRead {
  const meta = item.meta_json || {};
  return {
    id: rememberLegacyId("tag", item.id),
    tag_id: item.tag_id,
    owner_uid: null,
    name: item.tag_id,
    brief: item.brief,
    priority: typeof meta.priority === "number" ? meta.priority : 0,
    visibility_mode: item.is_isolated ? "private" : "public",
    group_allowlist_json: JSON.stringify(meta.group_allowlist ?? []),
    group_denylist_json: JSON.stringify(meta.group_denylist ?? []),
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

function mapMessage(item: {
  id: string;
  cocoon_id: string;
  action_id: string | null;
  client_request_id: string | null;
  role: string;
  content: string;
  is_thought: boolean;
  created_at: string;
}): import("./types").MessageRead {
  return {
    id: rememberLegacyId("message", item.id),
    message_uid: item.id,
    cocoon_id: rememberLegacyId("cocoon", item.cocoon_id),
    chat_group_id: null,
    source_cocoon_id: null,
    origin_cocoon_id: null,
    role: item.role,
    content: item.content,
    is_thought: item.is_thought,
    visibility_level: 0,
    delivery_status: "done",
    processing_status: "done",
    reply_to_message_id: null,
    created_at: item.created_at,
    updated_at: item.created_at,
  };
}

function mapMemory(item: {
  id: string;
  cocoon_id?: string;
  source_message_id?: string | null;
  scope: string;
  content: string;
  summary: string | null;
  tags_json: string[];
  created_at: string;
}): MemoryChunkRead {
  return {
    id: rememberLegacyId("memory", item.id),
    cocoon_id: item.cocoon_id ? rememberLegacyId("cocoon", item.cocoon_id) : 0,
    origin_cocoon_id: null,
    source_message_id: item.source_message_id ? rememberLegacyId("message", item.source_message_id) : null,
    chroma_document_id: item.id,
    role_key: item.scope,
    source_kind: item.scope,
    content: item.summary || item.content,
    visibility: 0,
    importance: 0,
    timestamp: new Date(item.created_at).getTime(),
    is_thought: false,
    is_summary: Boolean(item.summary),
    created_at: item.created_at,
    source_message: null,
    tags: item.tags_json,
  };
}

function mapRuntimeEvent(event: any): RuntimeWsEvent {
  if (event.type === "reply_started") {
    if (event.user_message) {
      return { ...event, user_message: mapMessage(event.user_message) };
    }
    return event as RuntimeWsEvent;
  }
  if (event.type === "reply_chunk") {
    return {
      ...event,
      delta: typeof event.delta === "string" ? event.delta : typeof event.text === "string" ? event.text : "",
      flush: Boolean(event.flush),
    } as RuntimeWsEvent;
  }
  if (event.type === "reply_done") {
    if (event.assistant_message) {
      return { ...event, assistant_message: mapMessage(event.assistant_message) };
    }
    return event as RuntimeWsEvent;
  }
  if (event.type === "state_patch") {
    return {
      ...event,
      current_wakeup_task_id: event.current_wakeup_task_id ?? null,
      current_model_id: event.current_model_id ? rememberLegacyId("model", event.current_model_id) : null,
    } satisfies StatePatchEvent;
  }
  return event as RuntimeWsEvent;
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
    const created = await client.createCocoon({
      name: data.name.trim(),
      character_id: resolveActualId("character", data.character_id || 0),
      selected_model_id: resolveActualId("model", data.selected_model_id || 0),
      parent_id: data.parent_id ? resolveActualId("cocoon", data.parent_id) : null,
      default_temperature: data.default_temperature ?? 0.7,
      max_context_messages: data.max_context_messages ?? data.max_context_tokens ?? 12,
    });
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
    });
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
    const all = (await client.listMessages(actualCocoonId)).map(mapMessage);
    const beforeActual = before_message_id ? resolveActualId("message", before_message_id) : null;
    const beforeIndex = beforeActual ? all.findIndex((item) => item.message_uid === beforeActual) : all.length;
    const end = beforeIndex >= 0 ? beforeIndex : all.length;
    const start = Math.max(0, end - page_size);
    const items = all.slice(start, end);
    return {
      items,
      total: all.length,
      page: 1,
      page_size,
      total_pages: 1,
    };
  });
}

export function getCocoonMemories(cocoon_id: number, page: number, page_size: number): Promise<PageResp<MemoryChunkRead>> {
  return apiCall(async (client) => {
    const items = (await client.listMemory(resolveActualId("cocoon", cocoon_id))).map((item) =>
      mapMemory({ ...item, cocoon_id: resolveActualId("cocoon", cocoon_id), source_message_id: null }),
    );
    return makePage(items, page, page_size);
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
      user_message: {
        id: rememberLegacyId("message", `pending:${accepted.action_id}`),
        message_uid: `pending:${accepted.action_id}`,
        cocoon_id,
        chat_group_id: null,
        source_cocoon_id: null,
        origin_cocoon_id: null,
        role: "user",
        content: data.content,
        is_thought: false,
        visibility_level: 0,
        delivery_status: "pending",
        processing_status: "queued",
        reply_to_message_id: null,
        created_at: new Date().toISOString(),
        updated_at: null,
      },
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
    handlers.onMessage(mapRuntimeEvent(JSON.parse(String(event.data))));
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
