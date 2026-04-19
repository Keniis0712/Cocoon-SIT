import { rememberLegacyId, rememberLegacyStringId } from "@/api/id-map";
import type { MessageRead } from "@/api/types/chat";

type RawWorkspaceMessage = {
  id: string;
  cocoon_id: string | null;
  chat_group_id?: string | null;
  sender_user_id?: string | null;
  role: string;
  content: string;
  is_thought: boolean;
  is_retracted?: boolean;
  retracted_at?: string | null;
  retracted_by_user_id?: string | null;
  retraction_note?: string | null;
  created_at: string;
};

type PendingWorkspaceTarget =
  | { kind: "cocoon"; targetId: number }
  | { kind: "chat-group"; targetId: string };

export function mapWorkspaceMessage(item: RawWorkspaceMessage): MessageRead {
  return {
    id: rememberLegacyId("message", item.id),
    message_uid: item.id,
    cocoon_id: item.cocoon_id ? rememberLegacyId("cocoon", item.cocoon_id) : null,
    chat_group_id: item.chat_group_id ? rememberLegacyId("group", item.chat_group_id) : null,
    source_cocoon_id: null,
    origin_cocoon_id: null,
    sender_user_id: item.sender_user_id ? rememberLegacyStringId("user", item.sender_user_id) : null,
    role: item.role,
    content: item.content,
    is_thought: item.is_thought,
    is_retracted: item.is_retracted ?? false,
    retracted_at: item.retracted_at ?? null,
    retracted_by_user_id: item.retracted_by_user_id ? rememberLegacyStringId("user", item.retracted_by_user_id) : null,
    retraction_note: item.retraction_note ?? null,
    visibility_level: 0,
    delivery_status: item.is_retracted ? "retracted" : "done",
    processing_status: item.is_retracted ? "retracted" : "done",
    reply_to_message_id: null,
    created_at: item.created_at,
    updated_at: item.retracted_at ?? item.created_at,
  };
}

export function createPendingUserMessage(actionId: string, content: string, target: PendingWorkspaceTarget): MessageRead {
  return {
    id: rememberLegacyId("message", `pending:${actionId}`),
    message_uid: `pending:${actionId}`,
    cocoon_id: target.kind === "cocoon" ? target.targetId : null,
    chat_group_id: target.kind === "chat-group" ? rememberLegacyId("group", target.targetId) : null,
    source_cocoon_id: null,
    origin_cocoon_id: null,
    sender_user_id: null,
    role: "user",
    content,
    is_thought: false,
    is_retracted: false,
    retracted_at: null,
    retracted_by_user_id: null,
    retraction_note: null,
    visibility_level: 0,
    delivery_status: "pending",
    processing_status: "queued",
    reply_to_message_id: null,
    created_at: new Date().toISOString(),
    updated_at: null,
  };
}

