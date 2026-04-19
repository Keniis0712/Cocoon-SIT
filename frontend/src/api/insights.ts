import { apiCall } from "./client";
import type { InsightsOverview, MemoryInsights, NamedMetric, RuntimeInsights, TokenUsageSeries } from "./types/insights";

function toNamedMetrics(record: Record<string, number>): NamedMetric[] {
  return Object.entries(record).map(([name, value]) => ({ name, value }));
}

function metricValue(metrics: { name: string; value: number }[], key: string) {
  return metrics.find((item) => item.name === key)?.value || 0;
}

function bucketMetrics(items: Array<{ name: string; value: number } | { provider_kind?: string; model_name?: string; total_tokens?: number }>, key: "provider_kind" | "model_name") {
  const buckets = new Map<string, number>();
  for (const item of items) {
    const name = String((item as Record<string, unknown>)[key] || "unknown");
    const value = Number((item as Record<string, unknown>).total_tokens ?? (item as Record<string, unknown>).value ?? 0);
    buckets.set(name, (buckets.get(name) || 0) + value);
  }
  return Array.from(buckets.entries()).map(([name, value]) => ({ name, value }));
}

export function getInsightsOverview(_params?: { range?: string }): Promise<InsightsOverview> {
  return apiCall(async (client) => {
    const summary = await client.getInsights();
    return {
      range: _params?.range || "30d",
      total_messages: metricValue(summary.metrics, "messages"),
      total_runs: metricValue(summary.metrics, "runs"),
      total_tokens: metricValue(summary.metrics, "tokens"),
      error_rate: metricValue(summary.metrics, "error_rate"),
      average_latency_ms: metricValue(summary.metrics, "avg_latency_ms"),
      active_cocoons: metricValue(summary.metrics, "active_cocoons"),
      pending_wakeup_count: metricValue(summary.metrics, "pending_wakeups"),
    };
  });
}

export function getTokenUsage(_params?: { range?: string; interval?: string }): Promise<TokenUsageSeries> {
  return apiCall(async (client) => {
    const summary = await client.getInsights();
    const totalTokens = metricValue(summary.metrics, "tokens");
    return {
      range: _params?.range || "30d",
      interval: _params?.interval || "day",
      total_tokens: totalTokens,
      series: [{ bucket: _params?.range || "30d", value: totalTokens }],
      by_provider: bucketMetrics(summary.model_usage, "provider_kind"),
      by_model: bucketMetrics(summary.model_usage, "model_name"),
      by_operation: toNamedMetrics(summary.operation_counts),
    };
  });
}

export function getMemoryInsights(_params?: { range?: string }): Promise<MemoryInsights> {
  return apiCall(async (client) => {
    const summary = await client.getInsights();
    const totalMemories = metricValue(summary.metrics, "memories");
    return {
      range: _params?.range || "30d",
      total_memories: totalMemories,
      growth: [{ bucket: _params?.range || "30d", value: totalMemories }],
      by_source_kind: [],
      by_visibility: [],
      by_memory_type: [],
      top_cocoons: [],
    };
  });
}

export function getRuntimeInsights(_params?: { range?: string; interval?: string }): Promise<RuntimeInsights> {
  return apiCall(async (client) => {
    const summary = await client.getInsights();
    const totalRuns = metricValue(summary.metrics, "runs");
    const wakeupRuns = summary.workflow_metrics.wakeup_runs || 0;
    const errorRate = metricValue(summary.metrics, "error_rate");
    return {
      range: _params?.range || "30d",
      interval: _params?.interval || "day",
      request_series: [{ bucket: _params?.range || "30d", value: totalRuns }],
      decision_distribution: [],
      status_distribution: toNamedMetrics(summary.action_status_counts),
      operation_distribution: toNamedMetrics(summary.operation_counts),
      node_latency: [],
      latency_p50_ms: 0,
      latency_p95_ms: metricValue(summary.metrics, "avg_latency_ms"),
      silence_rate: 0,
      wakeup_rate: totalRuns > 0 ? wakeupRuns / totalRuns : 0,
      error_rate: errorRate,
      top_error_cocoons: [],
    };
  });
}
