import type { MessageRead } from "./chat";
import type { CharacterRead, TagRead } from "./catalog";
import type { PageResp } from "./common";
import type { ChatGroupRead } from "./chat-groups";
import type { AvailableModelRead, ModelProviderRead } from "./providers";

export interface CocoonRead {
  id: number;
  name: string;
  owner_uid: string | null;
  default_temperature?: number | null;
  max_context_messages?: number | null;
  auto_compaction_enabled?: boolean | null;
  memory_profile?: string | null;
  kind: "private" | "group" | string;
  chat_group_id: number | null;
  parent_id: number | null;
  last_read_msg_id: number | null;
  debounce_until: string | null;
  dispatch_status: string;
  sync_mode: string;
  fork_anchor_msg_id: number | null;
  fork_at_msg_id: number | null;
  fork_at_ts: string | null;
  active_checkpoint_id: number | null;
  rollback_activated_at: string | null;
  context_prompt: string | null;
  max_context_tokens: number | null;
  max_rounds: number | null;
  compact_memory_max_items: number;
  auto_compaction_trigger_rounds: number;
  auto_compaction_message_count: number;
  auto_compaction_memory_max_items: number;
  manual_compaction_message_count: number;
  manual_compaction_memory_max_items: number;
  manual_compaction_mode: string;
  character_id: number;
  provider_id: number;
  selected_model_id: number;
  created_at: string;
  chat_group?: ChatGroupRead | null;
  character?: CharacterRead | null;
  provider?: ModelProviderRead | null;
  selected_model?: AvailableModelRead | null;
  tags?: TagRead[];
  dispatch_job?: DispatchJobRead | null;
}

export interface CocoonPayload {
  name: string;
  default_temperature?: number | null;
  max_context_messages?: number | null;
  auto_compaction_enabled?: boolean | null;
  memory_profile?: string | null;
  kind?: "private" | "group" | string;
  chat_group_id?: number | null;
  parent_id?: number | null;
  sync_mode?: string | null;
  context_prompt?: string | null;
  max_context_tokens?: number | null;
  max_rounds?: number | null;
  compact_memory_max_items?: number | null;
  auto_compaction_trigger_rounds?: number | null;
  auto_compaction_message_count?: number | null;
  auto_compaction_memory_max_items?: number | null;
  manual_compaction_message_count?: number | null;
  manual_compaction_memory_max_items?: number | null;
  manual_compaction_mode?: string | null;
  character_id?: number | null;
  selected_model_id?: number | null;
}

export interface CocoonTreeNode {
  id: number;
  name: string;
  owner_uid: string | null;
  kind: "private" | "group" | string;
  chat_group_id: number | null;
  parent_id: number | null;
  last_read_msg_id: number | null;
  debounce_until: string | null;
  dispatch_status: string;
  sync_mode: string;
  fork_anchor_msg_id: number | null;
  fork_at_msg_id: number | null;
  fork_at_ts: string | null;
  active_checkpoint_id: number | null;
  rollback_activated_at: string | null;
  context_prompt: string | null;
  max_context_tokens: number | null;
  max_rounds: number | null;
  compact_memory_max_items: number;
  auto_compaction_trigger_rounds: number;
  auto_compaction_message_count: number;
  auto_compaction_memory_max_items: number;
  manual_compaction_message_count: number;
  manual_compaction_memory_max_items: number;
  manual_compaction_mode: string;
  character_id: number;
  provider_id: number;
  selected_model_id: number;
  created_at: string;
  has_children: boolean;
  children: CocoonTreeNode[];
}

export interface CocoonTreeResponse extends PageResp<CocoonTreeNode> {
  parent_id: number | null;
  max_depth: number;
}

export interface MemoryChunkRead {
  id: number;
  cocoon_id: number | null;
  chat_group_id?: number | null;
  owner_user_id?: string | null;
  memory_pool: string;
  memory_type: string;
  status: string;
  summary: string | null;
  valid_until: string | null;
  last_accessed_at: string | null;
  access_count: number;
  meta_json?: Record<string, unknown>;
  origin_cocoon_id: number | null;
  source_message_id: number | null;
  chroma_document_id: string;
  role_key: string;
  source_kind: string;
  content: string;
  visibility: number;
  importance: number;
  confidence?: number;
  timestamp: number;
  is_thought: boolean;
  is_summary: boolean;
  created_at: string;
  source_message?: MessageRead | null;
  tags?: string[];
}

export interface MemoryOverviewRead {
  total: number;
  by_pool: Record<string, number>;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  tag_cloud: Array<{ tag: string; count: number }>;
  importance_average: number;
  confidence_average: number;
}

export interface MemoryListRead {
  items: MemoryChunkRead[];
  overview: MemoryOverviewRead;
}

export interface CocoonCompactionPayload {
  mode?: string;
  message_count?: number | null;
  memory_max_items?: number | null;
}

export interface CocoonCompactionResult {
  triggered: boolean;
  mode: string;
  selected_message_count: number;
  persisted_count: number;
  compacted_until_message_id: number | null;
  summary: string;
  reason?: string | null;
  items: Record<string, unknown>[];
}

export interface DurableJobRead {
  id: string;
  cocoon_id: string | null;
  job_type: string;
  status: string;
  lock_key: string;
  payload_json: Record<string, unknown>;
  available_at: string;
  started_at: string | null;
  finished_at: string | null;
  worker_name: string | null;
  error_text: string | null;
}

export interface DispatchJobRead {
  id: number;
  cocoon_id: number;
  status: string;
  debounce_until: string | null;
  typing_hint_until: string | null;
  max_enqueued_msg_id: number | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}
