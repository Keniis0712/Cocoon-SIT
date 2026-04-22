export type WakeupTargetType = "cocoon" | "chat_group";

export type WakeupStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface WakeupTaskRead {
  id: string;
  target_type: WakeupTargetType;
  target_id: string;
  target_name: string | null;
  run_at: string;
  reason: string | null;
  status: WakeupStatus | string;
  scheduled_by: string | null;
  trigger_kind: string | null;
  is_ai_wakeup: boolean;
  cancelled_at: string | null;
  cancelled_reason: string | null;
  created_at: string;
}
