import { apiCall } from "./client";
import { rememberLegacyId, resolveActualId } from "./id-map";
import type {
  CocoonMergeCreatePayload,
  CocoonMergeJobDetail,
  CocoonMergeJobRead,
  PageResp,
} from "./types";

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

function mapMergeJob(item: {
  id: string;
  source_cocoon_id: string;
  target_cocoon_id: string;
  status: string;
  summary_json: Record<string, unknown>;
  created_at: string;
}): CocoonMergeJobRead {
  return {
    id: rememberLegacyId("merge", item.id),
    merge_uid: item.id,
    source_cocoon_id: rememberLegacyId("cocoon", item.source_cocoon_id),
    target_cocoon_id: rememberLegacyId("cocoon", item.target_cocoon_id),
    source_checkpoint_id: null,
    target_checkpoint_id: null,
    strategy: typeof item.summary_json.strategy === "string" ? item.summary_json.strategy : "subtle",
    status: item.status,
    model_name: null,
    candidate_count: Number(item.summary_json.candidate_count || 0),
    merged_count: Number(item.summary_json.merged_count || 0),
    created_by: null,
    applied_state_delta_json: JSON.stringify(item.summary_json),
    merge_summary_message_id: null,
    error_detail: null,
    started_at: null,
    finished_at: null,
    created_at: item.created_at,
  };
}

export function createMergeJob(data: CocoonMergeCreatePayload): Promise<CocoonMergeJobRead> {
  return apiCall(async (client) => {
    const result = await client.enqueueMerge({
      source_cocoon_id: resolveActualId("cocoon", data.source_cocoon_id),
      target_cocoon_id: resolveActualId("cocoon", data.target_cocoon_id),
    });
    const jobs = await client.listMerges();
    const created = jobs.find((item) => item.id === result.merge_job_id) || jobs[0];
    if (!created) {
      throw new Error("Merge job was created but could not be loaded");
    }
    return mapMergeJob(created);
  });
}

export function listMergeJobs(
  page: number,
  page_size: number,
  params?: {
    scope?: "mine" | "all";
    status?: string;
    source_cocoon_id?: number;
    target_cocoon_id?: number;
    merge_uid?: string;
    q?: string;
  },
): Promise<PageResp<CocoonMergeJobRead>> {
  return apiCall(async (client) => {
    const items = (await client.listMerges())
      .map(mapMergeJob)
      .filter((item) => !params?.status || item.status === params.status)
      .filter((item) => !params?.merge_uid || item.merge_uid.includes(params.merge_uid))
      .filter((item) => !params?.source_cocoon_id || item.source_cocoon_id === params.source_cocoon_id)
      .filter((item) => !params?.target_cocoon_id || item.target_cocoon_id === params.target_cocoon_id)
      .filter((item) => !params?.q || item.merge_uid.includes(params.q));
    return makePage(items, page, page_size);
  });
}

export function getMergeJobDetail(mergeUid: string): Promise<CocoonMergeJobDetail> {
  return apiCall(async (client) => {
    const job = (await client.listMerges()).find((item) => item.id === resolveActualId("merge", mergeUid));
    if (!job) {
      throw new Error("Merge job not found");
    }
    return {
      ...mapMergeJob(job),
      trace: job.summary_json,
    };
  });
}
