import { getAuditRun, listAuditRuns } from "./adminAudits";
import type { AiAuditTraceDetail, AiAuditTraceListItem, PageResp } from "./types";

export function listCocoonAuditRounds(
  cocoonId: number,
  params: {
    page: number;
    page_size: number;
    q?: string;
    round_uid?: string;
  },
): Promise<PageResp<AiAuditTraceListItem>> {
  return listAuditRuns({
    page: params.page,
    page_size: params.page_size,
    cocoon_id: cocoonId,
    q: params.q,
    round_uid: params.round_uid,
  });
}

export function getCocoonAuditRound(_cocoonId: number, auditId: number): Promise<AiAuditTraceDetail> {
  return getAuditRun(auditId);
}
