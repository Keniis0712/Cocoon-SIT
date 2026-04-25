import { apiCall } from "./client";
import { rememberLegacyId, resolveActualId } from "./id-map";
import type { AuditRunDetail, AuditRunListItem, AuditTimelineItem, PageResp } from "./types";

type RawAuditArtifact = {
  id: string;
  kind: string;
  summary?: string | null;
  metadata_json?: Record<string, unknown>;
  payload_json?: unknown;
  created_at: string;
};

type RawAuditStep = {
  id: string;
  step_name: string;
  status: string;
  started_at: string;
  finished_at: string | null;
};

type RawAuditRun = {
  id: string;
  cocoon_id: string | null;
  action_id: string | null;
  user_message_id?: string | null;
  assistant_message_id?: string | null;
  trigger_input?: string | null;
  assistant_output?: string | null;
  operation_type: string;
  status: string;
  started_at: string;
  finished_at: string | null;
};

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

function numericId(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 33 + value.charCodeAt(index)) >>> 0;
  }
  return hash || 1;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function mapStatus(status: string) {
  if (status === "completed") return "success";
  if (status === "failed") return "error";
  return status;
}

function inferTriggerType(operationType: string) {
  if (operationType === "wakeup") return "wakeup_timer";
  if (operationType === "pull") return "pull_request";
  if (operationType === "merge") return "merge_request";
  return "user_message";
}

function findArtifact(artifacts: RawAuditArtifact[], kind: string) {
  return artifacts.find((item) => item.kind === kind);
}

function mapAuditRun(item: RawAuditRun): AuditRunListItem {
  const userMessageContent = typeof item.trigger_input === "string" ? item.trigger_input : null;
  const assistantOutput = typeof item.assistant_output === "string" ? item.assistant_output : null;
  return {
    id: rememberLegacyId("audit", item.id),
    round_uid: item.id,
    cocoon_id: item.cocoon_id ? rememberLegacyId("cocoon", item.cocoon_id) : 0,
    user_message_id: item.user_message_id ? rememberLegacyId("message", item.user_message_id) : null,
    assistant_message_id: item.assistant_message_id ? rememberLegacyId("message", item.assistant_message_id) : null,
    trigger_event_uid: item.action_id,
    trigger_input: userMessageContent,
    trigger_type: inferTriggerType(item.operation_type),
    operation_type: item.operation_type,
    decision: null,
    status: mapStatus(item.status),
    provider_name: null,
    model_name: null,
    token_prompt: null,
    token_completion: null,
    token_total: null,
    latency_ms:
      item.finished_at && item.started_at
        ? Math.max(0, new Date(item.finished_at).getTime() - new Date(item.started_at).getTime())
        : null,
    schedule_action: null,
    scheduled_wakeup_at: null,
    internal_thought: null,
    error_detail: item.status === "failed" ? "Audit run failed" : null,
    has_state_delta: false,
    has_error: item.status === "failed",
    started_at: item.started_at,
    finished_at: item.finished_at,
    created_at: item.started_at,
    user_message: userMessageContent
      ? {
          id: item.user_message_id ? rememberLegacyId("message", item.user_message_id) : rememberLegacyId("message", `trigger-${item.id}`),
          message_uid: item.user_message_id || `trigger-${item.id}`,
          cocoon_id: item.cocoon_id ? rememberLegacyId("cocoon", item.cocoon_id) : 0,
          chat_group_id: null,
          source_cocoon_id: null,
          origin_cocoon_id: null,
          role: "user",
          content: userMessageContent,
          is_thought: false,
          visibility_level: 0,
          delivery_status: "delivered",
          processing_status: "completed",
          reply_to_message_id: null,
          created_at: item.started_at,
          updated_at: null,
        }
      : null,
    assistant_message: assistantOutput
      ? {
          id: item.assistant_message_id ? rememberLegacyId("message", item.assistant_message_id) : rememberLegacyId("message", `assistant-${item.id}`),
          message_uid: item.assistant_message_id || `assistant-${item.id}`,
          cocoon_id: item.cocoon_id ? rememberLegacyId("cocoon", item.cocoon_id) : 0,
          chat_group_id: null,
          source_cocoon_id: null,
          origin_cocoon_id: null,
          role: "assistant",
          content: assistantOutput,
          is_thought: false,
          visibility_level: 0,
          delivery_status: "delivered",
          processing_status: "completed",
          reply_to_message_id: null,
          created_at: item.finished_at || item.started_at,
          updated_at: null,
        }
      : null,
    assistant_output: assistantOutput,
  };
}

function buildRunDetail(run: RawAuditRun, steps: RawAuditStep[], artifacts: RawAuditArtifact[], links: Array<{
  id: string;
  relation: string;
  source_artifact_id: string | null;
  source_step_id: string | null;
  target_artifact_id: string | null;
  target_step_id: string | null;
  created_at: string;
}>): AuditRunDetail {
  const base = mapAuditRun(run);
  const metaOutput = asRecord(findArtifact(artifacts, "meta_output")?.payload_json);
  const providerRaw = findArtifact(artifacts, "provider_raw_output");
  const generatorOutput = asRecord(findArtifact(artifacts, "generator_output")?.payload_json);
  const workflowSummary = asRecord(findArtifact(artifacts, "workflow_summary")?.payload_json);
  const sideEffects = asRecord(findArtifact(artifacts, "side_effects_result")?.payload_json);
  const providerMeta = asRecord(providerRaw?.metadata_json) ?? {};
  const wakeupTaskId = typeof workflowSummary?.wakeup_task_id === "string" ? workflowSummary.wakeup_task_id : null;
  const compactionJobId = typeof workflowSummary?.compaction_job_id === "string" ? workflowSummary.compaction_job_id : null;

  return {
    ...base,
    decision: typeof metaOutput?.decision === "string" ? metaOutput.decision : null,
    model_name:
      typeof providerMeta.model_name === "string"
        ? providerMeta.model_name
        : typeof generatorOutput?.model_name === "string"
          ? generatorOutput.model_name
          : null,
    token_prompt: typeof providerMeta.prompt_tokens === "number" ? providerMeta.prompt_tokens : null,
    token_completion: typeof providerMeta.completion_tokens === "number" ? providerMeta.completion_tokens : null,
    token_total: typeof providerMeta.total_tokens === "number" ? providerMeta.total_tokens : null,
    schedule_action: wakeupTaskId || compactionJobId ? [wakeupTaskId ? "wakeup" : null, compactionJobId ? "compaction" : null].filter(Boolean).join(" + ") : null,
    scheduled_wakeup_at: null,
    internal_thought: typeof metaOutput?.internal_thought === "string" ? metaOutput.internal_thought : null,
    has_state_delta: Boolean(sideEffects),
    assistant_message: typeof generatorOutput?.content === "string"
      ? {
          id: rememberLegacyId("message", String(generatorOutput.final_message_id || `generator-${run.id}`)),
          message_uid: String(generatorOutput.final_message_id || `generator-${run.id}`),
          cocoon_id: base.cocoon_id,
          chat_group_id: null,
          source_cocoon_id: null,
          origin_cocoon_id: null,
          role: "assistant",
          content: generatorOutput.content,
          is_thought: false,
          visibility_level: 0,
          delivery_status: "delivered",
          processing_status: "completed",
          reply_to_message_id: null,
          created_at: run.finished_at || run.started_at,
          updated_at: null,
        }
      : base.assistant_message,
    steps: steps.map((item) => ({
      id: numericId(item.id),
      raw_uid: item.id,
      step_name: item.step_name,
      status: mapStatus(item.status),
      latency_ms:
        item.finished_at && item.started_at
          ? Math.max(0, new Date(item.finished_at).getTime() - new Date(item.started_at).getTime())
          : null,
      token_prompt: item.step_name === "generator_node" && typeof providerMeta.prompt_tokens === "number" ? providerMeta.prompt_tokens : null,
      token_completion: item.step_name === "generator_node" && typeof providerMeta.completion_tokens === "number" ? providerMeta.completion_tokens : null,
      token_total: item.step_name === "generator_node" && typeof providerMeta.total_tokens === "number" ? providerMeta.total_tokens : null,
      error_detail: null,
      started_at: item.started_at,
      finished_at: item.finished_at,
      created_at: item.started_at || "",
    })),
    artifacts: artifacts.map((item, index) => ({
      id: numericId(item.id),
      raw_uid: item.id,
      artifact_type: item.kind,
      title: item.summary ?? null,
      payload: item.payload_json ?? item.metadata_json ?? null,
      sort_order: index,
      created_at: item.created_at,
    })),
    links: links.map((item) => ({
      id: numericId(item.id),
      relation: item.relation,
      source_artifact_id: item.source_artifact_id,
      source_step_id: item.source_step_id,
      target_artifact_id: item.target_artifact_id,
      target_step_id: item.target_step_id,
      label: item.relation,
      created_at: item.created_at,
    })),
  };
}

export function listAuditRuns(params: {
  page: number;
  page_size: number;
  cocoon_id?: number;
  q?: string;
  round_uid?: string;
  trigger_type?: string;
  operation_type?: string;
  status?: string;
  decision?: string;
}): Promise<PageResp<AuditRunListItem>> {
  return apiCall(async (client) => {
    const items = (await client.listAudits())
      .map((item) => mapAuditRun(item as unknown as RawAuditRun))
      .filter((item) => !params.status || item.status === params.status)
      .filter((item) => !params.operation_type || item.operation_type === params.operation_type)
      .filter((item) => !params.trigger_type || item.trigger_type === params.trigger_type)
      .filter((item) => !params.round_uid || item.round_uid.includes(params.round_uid))
      .filter((item) => !params.cocoon_id || item.cocoon_id === params.cocoon_id)
      .filter((item) => !params.q || item.round_uid.includes(params.q) || item.trigger_event_uid?.includes(params.q));
    return makePage(items, params.page, params.page_size);
  });
}

export function getAuditRun(auditId: number): Promise<AuditRunDetail> {
  return apiCall(async (client) => {
    const detail = await client.getAudit(resolveActualId("audit", auditId));
    return buildRunDetail(
      detail.run as unknown as RawAuditRun,
      detail.steps as unknown as RawAuditStep[],
      detail.artifacts as unknown as RawAuditArtifact[],
      detail.links as unknown as Array<{
        id: string;
        relation: string;
        source_artifact_id: string | null;
        source_step_id: string | null;
        target_artifact_id: string | null;
        target_step_id: string | null;
        created_at: string;
      }>,
    );
  });
}

export function getAuditTimeline(params?: { cocoon_id?: number; limit?: number }): Promise<AuditTimelineItem[]> {
  return apiCall(async (client) => {
    const items = (await client.listAudits())
      .map((item) => mapAuditRun(item as unknown as RawAuditRun))
      .filter((item) => !params?.cocoon_id || item.cocoon_id === params.cocoon_id)
      .slice(0, params?.limit || 20);
    return items.map((item) => ({
      kind: "audit_run",
      cocoon_id: item.cocoon_id,
      occurred_at: item.created_at,
      status: item.status,
      label: item.operation_type,
      target_id: item.id,
      target_uid: item.round_uid,
      payload: {},
    }));
  });
}
