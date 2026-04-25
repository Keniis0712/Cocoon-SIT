import type { NamedMetric, RankedCocoonMetric, TimeSeriesPoint } from "./common";

export type { NamedMetric, RankedCocoonMetric, TimeSeriesPoint } from "./common";

export type InsightsRange = "24h" | "7d" | "30d" | "90d";
export type InsightsInterval = "auto" | "hour" | "day";
export type ResolvedInsightsInterval = "hour" | "day";

export interface InsightsSummary {
  total_messages: number;
  total_runs: number;
  total_tokens: number;
  error_rate: number;
  average_latency_ms: number;
  active_cocoons: number;
  pending_wakeup_count: number;
}

export interface TokenUsageInsights {
  series: TimeSeriesPoint[];
  by_provider: NamedMetric[];
  by_model: NamedMetric[];
  by_operation: NamedMetric[];
}

export interface MemoryInsights {
  total_memories: number;
  growth: TimeSeriesPoint[];
  by_source_kind: NamedMetric[];
  by_memory_type: NamedMetric[];
  top_cocoons: RankedCocoonMetric[];
}

export interface RuntimeInsights {
  request_series: TimeSeriesPoint[];
  decision_distribution: NamedMetric[];
  status_distribution: NamedMetric[];
  node_latency: NamedMetric[];
  latency_p50_ms: number;
  latency_p95_ms: number;
  silence_rate: number;
  wakeup_rate: number;
  error_rate: number;
  top_error_cocoons: RankedCocoonMetric[];
}

export interface InsightsDashboard {
  generated_at: string;
  range: InsightsRange;
  interval: ResolvedInsightsInterval;
  summary: InsightsSummary;
  token_usage: TokenUsageInsights;
  memory: MemoryInsights;
  runtime: RuntimeInsights;
}
