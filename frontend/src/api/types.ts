export interface PageResp<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface CharacterRead {
  id: number;
  name: string;
  owner_uid: string | null;
  visibility: "private" | "public" | string;
  description: string | null;
  personality_prompt: string;
  created_at: string;
}

export interface CharacterPayload {
  name: string;
  description?: string | null;
  personality_prompt: string;
  visibility?: "private" | "public";
}

export interface CharacterAclEntryRead {
  id: number;
  character_id: number;
  grantee_type: "USER" | "GROUP" | "SUBTREE" | "AUTHENTICATED_ALL" | string;
  grantee_id: string;
  perm_level: number;
  granted_by_uid: string | null;
  created_at: string;
  updated_at: string;
}

export interface CharacterAclEntryWrite {
  grantee_type: "USER" | "GROUP" | "SUBTREE" | "AUTHENTICATED_ALL";
  grantee_id: string;
  perm_level: "READ" | "USE" | "MANAGE";
}

export interface CharacterAclEffectiveEntry {
  source: string;
  grantee_id: string | null;
  perm_level: number;
}

export interface AvailableModelRead {
  id: number;
  provider_id: number;
  model_name: string;
  created_at: string;
  updated_at: string;
}

export interface ModelProviderRead {
  id: number;
  name: string;
  base_url: string;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
  available_models: AvailableModelRead[];
}

export interface ModelProviderPayload {
  name: string;
  base_url: string;
  api_key: string;
  is_enabled: boolean;
}

export interface StructuredModelTestRead {
  name: string;
  raw_text: string;
  parsed_result: Record<string, unknown>;
}

export interface ModelProviderTestResponse {
  provider_id: number;
  selected_model_id: number;
  model_name: string;
  reply: string;
  structured_tests: StructuredModelTestRead[];
}

export interface AllowedModelRead {
  id: number;
  provider_id: number;
  provider_name: string;
  model_name: string;
}

export interface PublicFeaturesRead {
  allow_registration: boolean;
  max_chat_turns: number;
  allowed_models: AllowedModelRead[];
  rollback_retention_days: number;
  rollback_cleanup_interval_hours: number;
}

export interface SystemSettingsRead {
  allow_registration: boolean;
  max_chat_turns: number;
  allowed_model_ids: number[];
  default_max_context_tokens: number;
  default_max_rounds: number;
  default_compact_memory_max_items: number;
  default_auto_compaction_trigger_rounds: number;
  default_auto_compaction_message_count: number;
  default_auto_compaction_memory_max_items: number;
  default_manual_compaction_message_count: number;
  default_manual_compaction_memory_max_items: number;
  default_manual_compaction_mode: string;
  dispatch_thread_pool_max_workers: number;
  llm_max_concurrency: number;
  embedding_max_concurrency: number;
  private_chat_debounce_ms: number;
  group_chat_debounce_ms: number;
  typing_debounce_max_extra_ms: number;
  idle_followup_medium_turn_threshold: number;
  idle_followup_high_turn_threshold: number;
  idle_followup_low_activity_seconds: number;
  idle_followup_medium_activity_seconds: number;
  idle_followup_high_activity_seconds: number;
  rollback_retention_days: number;
  rollback_cleanup_interval_hours: number;
  created_at: string;
  updated_at: string;
}

export interface SystemSettingsUpdate {
  allow_registration?: boolean;
  max_chat_turns?: number;
  allowed_model_ids?: number[];
  default_max_context_tokens?: number;
  default_max_rounds?: number;
  default_compact_memory_max_items?: number;
  default_auto_compaction_trigger_rounds?: number;
  default_auto_compaction_message_count?: number;
  default_auto_compaction_memory_max_items?: number;
  default_manual_compaction_message_count?: number;
  default_manual_compaction_memory_max_items?: number;
  default_manual_compaction_mode?: string;
  dispatch_thread_pool_max_workers?: number;
  llm_max_concurrency?: number;
  embedding_max_concurrency?: number;
  private_chat_debounce_ms?: number;
  group_chat_debounce_ms?: number;
  typing_debounce_max_extra_ms?: number;
  idle_followup_medium_turn_threshold?: number;
  idle_followup_high_turn_threshold?: number;
  idle_followup_low_activity_seconds?: number;
  idle_followup_medium_activity_seconds?: number;
  idle_followup_high_activity_seconds?: number;
  rollback_retention_days?: number;
  rollback_cleanup_interval_hours?: number;
}

export interface CocoonRead {
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
  chat_group?: ChatGroupRead | null;
  character?: CharacterRead | null;
  provider?: ModelProviderRead | null;
  selected_model?: AvailableModelRead | null;
  tags?: TagRead[];
  dispatch_job?: DispatchJobRead | null;
}

export interface CocoonPayload {
  name: string;
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

export interface MessageRead {
  id: number;
  message_uid: string;
  cocoon_id: number;
  chat_group_id: number | null;
  source_cocoon_id: number | null;
  origin_cocoon_id: number | null;
  role: string;
  content: string;
  is_thought: boolean;
  visibility_level: number;
  delivery_status: string;
  processing_status: string;
  reply_to_message_id: number | null;
  created_at: string;
  updated_at: string | null;
}

export interface MemoryChunkRead {
  id: number;
  cocoon_id: number;
  origin_cocoon_id: number | null;
  source_message_id: number | null;
  chroma_document_id: string;
  role_key: string;
  source_kind: string;
  content: string;
  visibility: number;
  importance: number;
  timestamp: number;
  is_thought: boolean;
  is_summary: boolean;
  created_at: string;
  source_message?: MessageRead | null;
  tags?: string[];
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

export interface TagRead {
  id: number;
  tag_id: string;
  owner_uid: string | null;
  name: string;
  brief: string;
  priority: number;
  visibility_mode: "public" | "private" | "group_acl" | string;
  group_allowlist_json: string;
  group_denylist_json: string;
  created_at: string;
  updated_at: string;
}

export interface TagPayload {
  name: string;
  brief?: string;
  priority?: number;
  visibility_mode?: "public" | "private" | "group_acl" | string;
  group_allowlist?: string[];
  group_denylist?: string[];
}

export interface ChatGroupRead {
  id: number;
  gid: string;
  name: string;
  owner_uid: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatGroupPayload {
  name: string;
  description?: string | null;
}

export interface EmbeddingProviderRead {
  id: number;
  name: string;
  kind: "local_cpu" | "openai_compatible" | string;
  base_url: string | null;
  model_name: string | null;
  local_model_name: string | null;
  device: string;
  is_enabled: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmbeddingProviderPayload {
  name: string;
  kind: "local_cpu" | "openai_compatible" | string;
  base_url?: string | null;
  api_key?: string | null;
  model_name?: string | null;
  local_model_name?: string | null;
  device?: string;
  is_enabled?: boolean;
  is_default?: boolean;
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

export interface AuditStepRead {
  id: number;
  step_name: string;
  status: string;
  latency_ms: number | null;
  token_prompt: number | null;
  token_completion: number | null;
  token_total: number | null;
  error_detail: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface AuditArtifactRead {
  id: number;
  artifact_type: string;
  title: string | null;
  payload: unknown;
  sort_order: number;
  created_at: string;
}

export interface AuditLinkRead {
  id: number;
  link_type: string;
  target_id: number | null;
  target_uid: string | null;
  label: string | null;
  created_at: string;
}

export interface AuditRunListItem {
  id: number;
  round_uid: string;
  cocoon_id: number;
  user_message_id: number | null;
  assistant_message_id: number | null;
  trigger_event_uid: string | null;
  trigger_type: string;
  operation_type: string;
  decision: string | null;
  status: string;
  provider_name: string | null;
  model_name: string | null;
  token_prompt: number | null;
  token_completion: number | null;
  token_total: number | null;
  latency_ms: number | null;
  schedule_action: string | null;
  scheduled_wakeup_at: string | null;
  internal_thought: string | null;
  error_detail: string | null;
  has_state_delta: boolean;
  has_error: boolean;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  user_message?: MessageRead | null;
  assistant_message?: MessageRead | null;
}

export interface AuditRunDetail extends AuditRunListItem {
  steps: AuditStepRead[];
  artifacts: AuditArtifactRead[];
  links: AuditLinkRead[];
}

export interface AuditTimelineItem {
  kind: string;
  cocoon_id: number;
  occurred_at: string;
  status: string | null;
  label: string;
  target_id: number | null;
  target_uid: string | null;
  payload: Record<string, unknown>;
}

export interface NamedMetric {
  name: string;
  value: number;
}

export interface TimeSeriesPoint {
  bucket: string;
  value: number;
}

export interface RankedCocoonMetric {
  cocoon_id: number;
  cocoon_name: string;
  value: number;
}

export interface InsightsOverview {
  range: string;
  total_messages: number;
  total_runs: number;
  total_tokens: number;
  error_rate: number;
  average_latency_ms: number;
  active_cocoons: number;
  pending_wakeup_count: number;
}

export interface TokenUsageSeries {
  range: string;
  interval: string;
  total_tokens: number;
  series: TimeSeriesPoint[];
  by_provider: NamedMetric[];
  by_model: NamedMetric[];
  by_operation: NamedMetric[];
}

export interface MemoryInsights {
  range: string;
  total_memories: number;
  growth: TimeSeriesPoint[];
  by_source_kind: NamedMetric[];
  by_visibility: NamedMetric[];
  by_memory_type: NamedMetric[];
  top_cocoons: RankedCocoonMetric[];
}

export interface RuntimeInsights {
  range: string;
  interval: string;
  request_series: TimeSeriesPoint[];
  decision_distribution: NamedMetric[];
  status_distribution: NamedMetric[];
  operation_distribution: NamedMetric[];
  node_latency: NamedMetric[];
  latency_p50_ms: number;
  latency_p95_ms: number;
  silence_rate: number;
  wakeup_rate: number;
  error_rate: number;
  top_error_cocoons: RankedCocoonMetric[];
}

export type AiAuditTraceListItem = AuditRunListItem;
export type AiAuditTraceDetail = AuditRunDetail & { trace?: Record<string, unknown> };

export interface AdminUserRead {
  uid: string;
  username: string;
  email: string | null;
  parent_uid: string | null;
  user_path: string;
  invite_code: string | null;
  role: string;
  role_level: number;
  can_audit: boolean;
  is_active: boolean;
  token_version: number;
  quota_tokens: number;
  invite_quota_remaining: number;
  invite_quota_unlimited: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminUserCreatePayload {
  username: string;
  password: string;
  email?: string | null;
  role: string;
  role_level: number;
  can_audit: boolean;
  parent_uid?: string | null;
  invite_quota_remaining?: number;
  invite_quota_unlimited?: boolean;
}

export interface AdminUserUpdatePayload {
  email?: string | null;
  role?: string | null;
  role_level?: number | null;
  can_audit?: boolean | null;
  is_active?: boolean | null;
  password?: string | null;
  invite_quota_remaining?: number | null;
  invite_quota_unlimited?: boolean | null;
}

export interface RoleRead {
  code: string;
  name: string;
  description: string | null;
  permissions_json: string;
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export interface GroupRead {
  gid: string;
  name: string;
  owner_uid: string;
  parent_group_id: string | null;
  group_path: string;
  invite_quota_remaining: number;
  invite_quota_unlimited: boolean;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface GroupCreatePayload {
  name: string;
  parent_group_id?: string | null;
  description?: string | null;
}

export interface GroupUpdatePayload {
  name?: string | null;
  parent_group_id?: string | null;
  description?: string | null;
  invite_quota_remaining?: number | null;
  invite_quota_unlimited?: boolean | null;
}

export interface GroupMemberRead {
  id: number;
  group_id: string;
  user_uid: string;
  created_at: string;
}

export interface InviteSummary {
  target_type: "USER" | "GROUP" | string;
  target_id: string;
  invite_quota_remaining: number;
  invite_quota_unlimited: boolean;
}

export interface InviteCodeRead {
  code: string;
  created_by_uid: string;
  parent_uid: string;
  source_type: "USER" | "GROUP" | "ADMIN_OVERRIDE" | string;
  source_id: string | null;
  expires_at: string | null;
  consumed_at: string | null;
  consumed_by_uid: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface InviteCodeCreatePayload {
  created_for_uid?: string | null;
  source_type: "USER" | "GROUP" | "ADMIN_OVERRIDE";
  source_id?: string | null;
  expires_at?: string | null;
  permanent?: boolean;
  prefix?: string | null;
}

export interface InviteQuotaGrantRead {
  id: number;
  granter_uid: string;
  target_type: "USER" | "GROUP" | string;
  target_id: string;
  amount: number;
  is_unlimited: boolean;
  note: string | null;
  created_at: string;
}

export interface InviteQuotaGrantCreatePayload {
  target_type: "USER" | "GROUP";
  target_id: string;
  amount: number;
  is_unlimited: boolean;
  note?: string | null;
}

export interface CocoonMergeCreatePayload {
  source_cocoon_id: number;
  target_cocoon_id: number;
  source_checkpoint_id?: number | null;
  target_checkpoint_id?: number | null;
  strategy: "archive" | "subtle" | "overhaul";
  include_dialogues: boolean;
  dialogue_strategy: "recent_only" | "balanced" | "all";
  max_dialogue_items: number;
  max_result_items: number;
}

export interface CocoonMergeJobRead {
  id: number;
  merge_uid: string;
  source_cocoon_id: number;
  target_cocoon_id: number;
  source_checkpoint_id: number | null;
  target_checkpoint_id: number | null;
  strategy: string;
  status: string;
  model_name: string | null;
  candidate_count: number;
  merged_count: number;
  created_by: string | null;
  applied_state_delta_json: string;
  merge_summary_message_id: number | null;
  error_detail: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface CocoonMergeJobDetail extends CocoonMergeJobRead {
  trace: Record<string, unknown>;
}

export interface InternalEventRead {
  id: number;
  event_uid: string;
  cocoon_id: number;
  event_type: string;
  payload_json: string;
  visible_in_chat: boolean;
  created_at: string;
}

export interface WakeupTaskRead {
  id: number;
  task_uid: string;
  cocoon_id: number;
  status: string;
  wakeup_at_utc: string;
  timezone: string | null;
  reason: string | null;
  trigger_metadata_json: string;
  decision_trace_json: string;
  superseded_by_task_id: number | null;
  created_at: string;
  updated_at: string;
  fired_at: string | null;
  cancelled_at: string | null;
}

export interface CocoonPullCreatePayload {
  source_cocoon_id: number;
  target_cocoon_id: number;
}

export interface CocoonPullJobRead {
  id: number;
  pull_uid: string;
  source_cocoon_id: number;
  target_cocoon_id: number;
  baseline_msg_id: number | null;
  baseline_ts: string | null;
  status: string;
  model_name: string | null;
  candidate_count: number;
  applied_count: number;
  created_by: string | null;
  applied_state_delta_json: string;
  summary_message_id: number | null;
  error_detail: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}
