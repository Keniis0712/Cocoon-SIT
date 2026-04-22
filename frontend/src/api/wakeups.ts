import { apiJson } from "./client";
import { resolveActualId } from "./id-map";
import type { WakeupStatus, WakeupTargetType, WakeupTaskRead } from "./types/wakeups";

type WakeupQuery = {
  status?: WakeupStatus | string;
  only_ai?: boolean;
  limit?: number;
  target_type?: WakeupTargetType;
  target_id?: string;
};

function withQuery(path: string, query?: WakeupQuery) {
  const params = new URLSearchParams();
  if (query?.status) {
    params.set("status", query.status);
  }
  if (query?.only_ai) {
    params.set("only_ai", "true");
  }
  if (typeof query?.limit === "number") {
    params.set("limit", String(query.limit));
  }
  if (query?.target_type) {
    params.set("target_type", query.target_type);
  }
  if (query?.target_id) {
    params.set("target_id", query.target_id);
  }
  const serialized = params.toString();
  return serialized ? `${path}?${serialized}` : path;
}

export function listAuditWakeups(query?: WakeupQuery) {
  return apiJson<WakeupTaskRead[]>(withQuery("/audits/wakeups", query));
}

export function listCocoonWakeups(cocoonId: number, query?: Omit<WakeupQuery, "target_type" | "target_id">) {
  return apiJson<WakeupTaskRead[]>(
    withQuery(`/cocoons/${resolveActualId("cocoon", cocoonId)}/wakeups`, query),
  );
}

export function listChatGroupWakeups(roomId: string, query?: Omit<WakeupQuery, "target_type" | "target_id">) {
  return apiJson<WakeupTaskRead[]>(withQuery(`/chat-groups/${roomId}/wakeups`, query));
}
