import { apiCall } from "./client";
import { rememberLegacyId, rememberLegacyStringId, resolveActualId } from "./id-map";
import type { AuditRunDetail, AuditRunListItem, AuditTimelineItem, PageResp } from "./types";

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

function mapAuditRun(item: {
  id: string;
  cocoon_id: string | null;
  action_id: string | null;
  operation_type: string;
  status: string;
  started_at: string;
  finished_at: string | null;
}): AuditRunListItem {
  return {
    id: rememberLegacyId("audit", item.id),
    round_uid: rememberLegacyStringId("audit", item.id),
    cocoon_id: item.cocoon_id ? rememberLegacyId("cocoon", item.cocoon_id) : 0,
    user_message_id: null,
    assistant_message_id: null,
    trigger_event_uid: item.action_id ? rememberLegacyStringId("message", item.action_id) : null,
    trigger_type: "user_message",
    operation_type: item.operation_type,
    decision: null,
    status: item.status,
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
    error_detail: item.status === "error" ? "Audit run failed" : null,
    has_state_delta: false,
    has_error: item.status === "error",
    started_at: item.started_at,
    finished_at: item.finished_at,
    created_at: item.started_at,
    user_message: null,
    assistant_message: null,
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
      .map(mapAuditRun)
      .filter((item) => !params.status || item.status === params.status)
      .filter((item) => !params.operation_type || item.operation_type === params.operation_type)
      .filter((item) => !params.round_uid || item.round_uid.includes(params.round_uid))
      .filter((item) => !params.cocoon_id || item.cocoon_id === params.cocoon_id)
      .filter((item) => !params.q || item.round_uid.includes(params.q));
    return makePage(items, params.page, params.page_size);
  });
}

export function getAuditRun(auditId: number): Promise<AuditRunDetail> {
  return apiCall(async (client) => {
    const detail = await client.getAudit(resolveActualId("audit", auditId));
    const run = mapAuditRun(detail.run);
    return {
      ...run,
      steps: detail.steps.map((item) => ({
        id: numericId(item.id),
        step_name: item.step_name,
        status: item.status,
        latency_ms:
          item.finished_at && item.started_at
            ? Math.max(0, new Date(item.finished_at).getTime() - new Date(item.started_at).getTime())
            : null,
        token_prompt: null,
        token_completion: null,
        token_total: null,
        error_detail: null,
        started_at: item.started_at,
        finished_at: item.finished_at,
        created_at: item.started_at || "",
      })),
      artifacts: detail.artifacts.map((item, index) => ({
        id: numericId(item.id),
        artifact_type: item.kind,
        title: item.summary,
        payload: item.metadata_json,
        sort_order: index,
        created_at: item.created_at,
      })),
      links: detail.links.map((item) => ({
        id: numericId(item.id),
        link_type: item.relation,
        target_id: null,
        target_uid: item.target_artifact_id || item.target_step_id,
        label: item.relation,
        created_at: item.created_at,
      })),
    };
  });
}

export function getAuditTimeline(params?: { cocoon_id?: number; limit?: number }): Promise<AuditTimelineItem[]> {
  return apiCall(async (client) => {
    const items = (await client.listAudits())
      .map(mapAuditRun)
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
