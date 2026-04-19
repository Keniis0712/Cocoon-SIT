import { apiCall, makeChatGroupWsUrl } from "./client";
import { createPendingUserMessage, mapWorkspaceMessage } from "./adapters/messages";
import { mapRuntimeWsEvent } from "./adapters/runtimeWs";
import { rememberLegacyId, rememberLegacyStringId, resolveActualId } from "./id-map";
import type { ChatEnqueueResponse, ChatRequest, MessageRead, MessageRetractResult, RuntimeWsEvent } from "./types/chat";
import type { ChatGroupMemberRead, ChatGroupPayload, ChatGroupRead, ChatGroupStateRead, ChatGroupUpdatePayload } from "./types/chat-groups";

function epochSecondsToIso(value: number | null | undefined) {
  if (typeof value !== "number") {
    return null;
  }
  return new Date(value * 1000).toISOString();
}

function mapRoom(item: {
  id: string;
  name: string;
  owner_user_id: string;
  character_id: string;
  selected_model_id: string;
  default_temperature: number;
  max_context_messages: number;
  auto_compaction_enabled: boolean;
  external_platform: string | null;
  external_group_id: string | null;
  external_account_id: string | null;
  created_at: string;
}): ChatGroupRead {
  return {
    id: item.id,
    name: item.name,
    owner_user_id: rememberLegacyStringId("user", item.owner_user_id),
    character_id: item.character_id,
    selected_model_id: item.selected_model_id,
    default_temperature: item.default_temperature,
    max_context_messages: item.max_context_messages,
    auto_compaction_enabled: item.auto_compaction_enabled,
    external_platform: item.external_platform,
    external_group_id: item.external_group_id,
    external_account_id: item.external_account_id,
    created_at: item.created_at,
  };
}

export function listChatGroups() {
  return apiCall(async (client) => (await client.listChatGroups()).map(mapRoom));
}

export function getChatGroup(roomId: string) {
  return apiCall(async (client) => mapRoom(await client.getChatGroup(roomId)));
}

export function createChatGroup(payload: ChatGroupPayload) {
  return apiCall(async (client) =>
    mapRoom(
      await client.createChatGroup({
        name: payload.name.trim(),
        character_id: resolveActualId("character", payload.character_id),
        selected_model_id: resolveActualId("model", payload.selected_model_id),
        default_temperature: payload.default_temperature ?? undefined,
        max_context_messages: payload.max_context_messages ?? undefined,
        auto_compaction_enabled: payload.auto_compaction_enabled ?? undefined,
        external_platform: payload.external_platform ?? null,
        external_group_id: payload.external_group_id ?? null,
        external_account_id: payload.external_account_id ?? null,
        initial_member_ids: (payload.initial_member_ids || []).map((item) => resolveActualId("user", item)),
      }),
    ),
  );
}

export function updateChatGroup(roomId: string, payload: ChatGroupUpdatePayload) {
  return apiCall(async (client) =>
    mapRoom(
      await client.updateChatGroup(roomId, {
        name: payload.name?.trim(),
        character_id: payload.character_id ? resolveActualId("character", payload.character_id) : undefined,
        selected_model_id: payload.selected_model_id ? resolveActualId("model", payload.selected_model_id) : undefined,
        default_temperature: payload.default_temperature ?? undefined,
        max_context_messages: payload.max_context_messages ?? undefined,
        auto_compaction_enabled: payload.auto_compaction_enabled ?? undefined,
        external_platform: payload.external_platform ?? undefined,
        external_group_id: payload.external_group_id ?? undefined,
        external_account_id: payload.external_account_id ?? undefined,
      }),
    ),
  );
}

export function deleteChatGroup(roomId: string) {
  return apiCall(async (client) => mapRoom(await client.deleteChatGroup(roomId)));
}

export function listChatGroupMembers(roomId: string) {
  return apiCall(async (client) =>
    (await client.listChatGroupMembers(roomId)).map(
      (item): ChatGroupMemberRead => ({
        id: item.id,
        room_id: item.room_id,
        user_id: rememberLegacyStringId("user", item.user_id),
        member_role: item.member_role,
        created_at: item.created_at,
      }),
    ),
  );
}

export function addChatGroupMember(roomId: string, userId: string, memberRole: "admin" | "member" = "member") {
  return apiCall(async (client) => {
    const item = await client.addChatGroupMember(roomId, {
      user_id: resolveActualId("user", userId),
      member_role: memberRole,
    });
    return {
      id: item.id,
      room_id: item.room_id,
      user_id: rememberLegacyStringId("user", item.user_id),
      member_role: item.member_role,
      created_at: item.created_at,
    } satisfies ChatGroupMemberRead;
  });
}

export function updateChatGroupMember(roomId: string, userId: string, memberRole: "admin" | "member") {
  return apiCall(async (client) => {
    const actualUserId = resolveActualId("user", userId);
    const item = await client.updateChatGroupMember(roomId, actualUserId, { member_role: memberRole });
    return {
      id: item.id,
      room_id: item.room_id,
      user_id: rememberLegacyStringId("user", item.user_id),
      member_role: item.member_role,
      created_at: item.created_at,
    } satisfies ChatGroupMemberRead;
  });
}

export function removeChatGroupMember(roomId: string, userId: string) {
  return apiCall(async (client) => {
    const actualUserId = resolveActualId("user", userId);
    const item = await client.removeChatGroupMember(roomId, actualUserId);
    return {
      id: item.id,
      room_id: item.room_id,
      user_id: rememberLegacyStringId("user", item.user_id),
      member_role: item.member_role,
      created_at: item.created_at,
    } satisfies ChatGroupMemberRead;
  });
}

export function listChatGroupMessages(roomId: string) {
  return apiCall(async (client) => (await client.listChatGroupMessages(roomId)).map(mapWorkspaceMessage));
}

export function sendChatGroupMessage(roomId: string, data: ChatRequest): Promise<ChatEnqueueResponse> {
  return apiCall(async (client) => {
    const accepted = await client.sendChatGroupMessage(roomId, {
      content: data.content,
      client_request_id: data.client_request_id || `${Date.now()}`,
      timezone: data.timezone ?? null,
    });
    return {
      accepted: accepted.accepted,
      dispatch_status: accepted.status,
      debounce_until: epochSecondsToIso(accepted.debounce_until),
      user_message: createPendingUserMessage(accepted.action_id, data.content, {
        kind: "chat-group",
        targetId: roomId,
      }),
    };
  });
}

export function retractChatGroupMessage(roomId: string, messageId: number | string) {
  return apiCall(async (client) => {
    const result = await client.retractChatGroupMessage(roomId, resolveActualId("message", messageId));
    return {
      message_id: result.message_id,
      is_retracted: result.is_retracted,
      retracted_at: result.retracted_at,
      retracted_by_user_id: result.retracted_by_user_id
        ? rememberLegacyStringId("user", result.retracted_by_user_id)
        : null,
      retraction_note: result.retraction_note,
    } satisfies MessageRetractResult;
  });
}

export function getChatGroupState(roomId: string) {
  return apiCall(async (client) => {
    const item = await client.getChatGroupState(roomId);
    return {
      id: item.id,
      cocoon_id: item.cocoon_id ?? null,
      chat_group_id: item.chat_group_id,
      relation_score: item.relation_score,
      persona_json: item.persona_json ?? {},
      active_tags_json: item.active_tags_json ?? [],
      current_wakeup_task_id: item.current_wakeup_task_id ?? null,
    } satisfies ChatGroupStateRead;
  });
}

export function connectChatGroupWorkspaceSocket(
  roomId: string,
  handlers: {
    onMessage: (event: RuntimeWsEvent) => void;
    onOpen?: () => void;
    onClose?: (event: CloseEvent) => void;
    onError?: (event: Event) => void;
  },
) {
  const socket = new WebSocket(makeChatGroupWsUrl(roomId));
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
