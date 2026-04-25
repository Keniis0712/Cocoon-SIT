import type { MessageRead } from "./chat";

export interface AuditStepRead {
  id: number;
  raw_uid?: string | null;
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
  raw_uid?: string | null;
  artifact_type: string;
  title: string | null;
  payload: unknown;
  sort_order: number;
  created_at: string;
}

export interface AuditLinkRead {
  id: number;
  relation: string;
  source_artifact_id: string | null;
  source_step_id: string | null;
  target_artifact_id: string | null;
  target_step_id: string | null;
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
  trigger_input: string | null;
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
  assistant_output?: string | null;
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

export type AiAuditTraceListItem = AuditRunListItem;
export type AiAuditTraceDetail = AuditRunDetail & { trace?: Record<string, unknown> };

