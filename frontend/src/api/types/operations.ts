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
