export interface MessageRead {
  id: number;
  message_uid: string;
  cocoon_id: number | null;
  chat_group_id: number | null;
  source_cocoon_id: number | null;
  origin_cocoon_id: number | null;
  sender_user_id?: string | null;
  role: string;
  content: string;
  is_thought: boolean;
  is_retracted?: boolean;
  retracted_at?: string | null;
  retracted_by_user_id?: string | null;
  retraction_note?: string | null;
  visibility_level: number;
  delivery_status: string;
  processing_status: string;
  reply_to_message_id: number | null;
  created_at: string;
  updated_at: string | null;
}

export interface ChatRequest {
  content: string;
  client_request_id?: string;
  client_sent_at?: string | null;
  timezone?: string | null;
  locale?: string | null;
  idle_seconds?: number | null;
  recent_turn_count?: number | null;
  typing_hint_ms?: number | null;
}

export interface ChatEnqueueResponse {
  accepted: boolean;
  dispatch_status: string;
  debounce_until: string | null;
  user_message: MessageRead;
}

export interface ChatMessagePage {
  items: MessageRead[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_more?: boolean;
}

export interface StatePatchEvent {
  type: "state_patch";
  relation_score: number;
  persona_json: Record<string, unknown>;
  active_tags: string[];
  current_wakeup_task_id?: string | null;
  current_model_id: number | null;
}

export interface RuntimeWsReplyStartedEvent {
  type: "reply_started";
  user_message_id: number;
  user_message: MessageRead;
}

export interface RuntimeWsReplyChunkEvent {
  type: "reply_chunk";
  delta: string;
  flush: boolean;
}

export interface RuntimeWsReplyDoneEvent {
  type: "reply_done";
  assistant_message: MessageRead;
}

export interface RuntimeWsRoundFailedEvent {
  type: "round_failed";
  failed_round_id: number;
  stage: string;
  retryable: boolean;
  error_detail: string;
  user_message_id: number | null;
  created_at: string | null;
}

export interface RuntimeWsDispatchQueuedEvent {
  type: "dispatch_queued";
  status?: string;
  reason?: string | null;
  debounce_until?: string | null;
}

export interface RuntimeWsMetaDoneEvent {
  type: "meta_done";
}

export interface RuntimeWsPongEvent {
  type: "pong";
}

export type RuntimeWsEvent =
  | RuntimeWsReplyStartedEvent
  | RuntimeWsReplyChunkEvent
  | RuntimeWsReplyDoneEvent
  | StatePatchEvent
  | RuntimeWsRoundFailedEvent
  | RuntimeWsDispatchQueuedEvent
  | RuntimeWsMetaDoneEvent
  | RuntimeWsPongEvent;

export interface ChatStreamStartEvent {
  type: "start";
  user_message?: MessageRead;
  assistant_message?: MessageRead;
}

export interface ChatStreamChunkEvent {
  type: "chunk";
  delta: string;
}

export interface ChatStreamDoneEvent {
  type: "done";
  assistant_message?: MessageRead;
  ignored: boolean;
  decision?: string;
  scheduled_wakeup_at?: string | null;
  scheduled_wakeup_timezone?: string | null;
}

export interface ChatStreamErrorEvent {
  type: "error";
  detail: string;
}

export type ChatStreamEvent =
  | ChatStreamStartEvent
  | ChatStreamChunkEvent
  | ChatStreamDoneEvent
  | ChatStreamErrorEvent;

export interface MessageRetractResult {
  message_id: string;
  is_retracted: boolean;
  retracted_at: string | null;
  retracted_by_user_id: string | null;
  retraction_note: string | null;
}
