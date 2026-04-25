import { apiCall } from "./client";
import type { InsightsDashboard, InsightsInterval, InsightsRange } from "./types/insights";

export function getInsightsDashboard(params?: {
  range?: InsightsRange;
  interval?: InsightsInterval;
}): Promise<InsightsDashboard> {
  return apiCall((client) =>
    client.getInsightsDashboard({
      range: params?.range,
      interval: params?.interval,
    }),
  );
}
