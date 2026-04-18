import { apiCall } from "./client";
import type { InsightsOverview, MemoryInsights, NamedMetric, RuntimeInsights, TokenUsageSeries } from "./types";

function toNamedMetrics(record: Record<string, number>): NamedMetric[] {
  return Object.entries(record).map(([name, value]) => ({ name, value }));
}

function metricValue(metrics: { name: string; value: number }[], key: string) {
  return metrics.find((item) => item.name === key)?.value || 0;
}

export function getInsightsOverview(_params?: { range?: string }): Promise<InsightsOverview> {
  return apiCall(async (client) => {
    const summary = await client.getInsights();
    return {
      range: "30d",
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
    return {
      range: "30d",
      interval: "day",
      total_tokens: metricValue(summary.metrics, "tokens"),
      series: [],
      by_provider: [],
      by_model: [],
      by_operation: toNamedMetrics(summary.operation_counts),
    };
  });
}

export function getMemoryInsights(_params?: { range?: string }): Promise<MemoryInsights> {
  return Promise.resolve({
    range: "30d",
    total_memories: 0,
    growth: [],
    by_source_kind: [],
    by_visibility: [],
    by_memory_type: [],
    top_cocoons: [],
  });
}

export function getRuntimeInsights(_params?: { range?: string; interval?: string }): Promise<RuntimeInsights> {
  return apiCall(async (client) => {
    const summary = await client.getInsights();
    return {
      range: "30d",
      interval: "day",
      request_series: [],
      decision_distribution: [],
      status_distribution: toNamedMetrics(summary.action_status_counts),
      operation_distribution: toNamedMetrics(summary.operation_counts),
      node_latency: [],
      latency_p50_ms: 0,
      latency_p95_ms: 0,
      silence_rate: 0,
      wakeup_rate: 0,
      error_rate: 0,
      top_error_cocoons: [],
    };
  });
}
