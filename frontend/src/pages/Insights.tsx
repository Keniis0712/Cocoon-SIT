import { useEffect, useMemo, useState } from "react";
import { Activity, BrainCircuit, Database, TimerReset } from "lucide-react";
import { useTranslation } from "react-i18next";

import { showErrorToast } from "@/api/client";
import { getInsightsDashboard } from "@/api/insights";
import type {
  InsightsDashboard,
  InsightsRange,
  NamedMetric,
  RankedCocoonMetric,
  TimeSeriesPoint,
} from "@/api/types/insights";
import AccessCard from "@/components/AccessCard";
import EChart from "@/components/charts/EChart";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { hasPermission } from "@/lib/permissions";
import { useUserStore } from "@/store/useUserStore";

function metricOption(items: NamedMetric[]) {
  return {
    tooltip: { trigger: "item" },
    legend: { bottom: 0 },
    series: [{ type: "pie", radius: ["45%", "70%"], data: items.map((item) => ({ name: item.name, value: item.value })) }],
  };
}

function seriesOption(points: TimeSeriesPoint[], color = "#2563eb") {
  return {
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: points.map((item) => item.bucket) },
    yAxis: { type: "value" },
    series: [{ type: "line", smooth: true, data: points.map((item) => item.value), areaStyle: {}, lineStyle: { color }, itemStyle: { color } }],
  };
}

function barOption(items: NamedMetric[]) {
  return {
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: items.map((item) => item.name), axisLabel: { rotate: 20 } },
    yAxis: { type: "value" },
    series: [{ type: "bar", data: items.map((item) => item.value), itemStyle: { borderRadius: [8, 8, 0, 0] } }],
  };
}

function topCocoonOption(items: RankedCocoonMetric[]) {
  return {
    tooltip: { trigger: "axis" },
    xAxis: { type: "value" },
    yAxis: { type: "category", data: items.map((item) => item.cocoon_name) },
    series: [{ type: "bar", data: items.map((item) => item.value), itemStyle: { borderRadius: [0, 8, 8, 0] } }],
  };
}

function SummaryCard({ title, value, hint }: { title: string; value: string | number; hint: string }) {
  return (
    <div className="rounded-2xl border border-border/70 p-4">
      <div className="mb-2 text-sm text-muted-foreground">{title}</div>
      <div className="text-2xl font-semibold">{value}</div>
      <div className="mt-2 text-xs text-muted-foreground">{hint}</div>
    </div>
  );
}

function EmptyChart({ message }: { message: string }) {
  return <div className="flex h-[280px] items-center justify-center text-sm text-muted-foreground">{message}</div>;
}

function hasMetricData(items: NamedMetric[]) {
  return items.some((item) => Number(item.value) > 0);
}

function hasSeriesData(points: TimeSeriesPoint[]) {
  return points.some((item) => Number(item.value) > 0);
}

function hasRankedData(items: RankedCocoonMetric[]) {
  return items.some((item) => Number(item.value) > 0);
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value: number) {
  return Math.round(value).toLocaleString();
}

export default function InsightsPage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const canView = hasPermission(userInfo, "insights:read");
  const [range, setRange] = useState<InsightsRange>("30d");
  const [dashboard, setDashboard] = useState<InsightsDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    if (!canView) return;
    async function loadData() {
      setIsLoading(true);
      setLoadFailed(false);
      try {
        const response = await getInsightsDashboard({ range, interval: "auto" });
        setDashboard(response);
      } catch (error) {
        setDashboard(null);
        setLoadFailed(true);
        showErrorToast(error, t("insights.loadFailed"));
      } finally {
        setIsLoading(false);
      }
    }
    void loadData();
  }, [canView, range, t]);

  const summary = useMemo(() => {
    if (!dashboard) return [];
    return [
      {
        title: t("insights.summary.totalTokens.title"),
        value: dashboard.summary.total_tokens.toLocaleString(),
        hint: t("insights.summary.totalTokens.hint"),
      },
      {
        title: t("insights.summary.auditRuns.title"),
        value: dashboard.summary.total_runs.toLocaleString(),
        hint: t("insights.summary.auditRuns.hint", { value: formatPercent(dashboard.runtime.silence_rate) }),
      },
      {
        title: t("insights.summary.memories.title"),
        value: dashboard.memory.total_memories.toLocaleString(),
        hint: t("insights.summary.memories.hint"),
      },
      {
        title: t("insights.summary.avgLatency.title"),
        value: `${formatNumber(dashboard.summary.average_latency_ms)} ms`,
        hint: t("insights.summary.avgLatency.hint", { value: formatNumber(dashboard.runtime.latency_p95_ms) }),
      },
    ];
  }, [dashboard, t]);

  if (!canView) return <AccessCard description={t("insights.noPermission")} />;

  return (
    <PageFrame
      title={t("insights.title")}
      description={t("insights.description")}
      actions={
        <div className="flex items-center gap-3">
          <Badge variant="outline">{t("insights.sqlBadge")}</Badge>
          <Select value={range} onValueChange={(value) => setRange(value as InsightsRange)}>
            <SelectTrigger className="w-[140px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="24h">{t("insights.ranges.24h")}</SelectItem>
              <SelectItem value="7d">{t("insights.ranges.7d")}</SelectItem>
              <SelectItem value="30d">{t("insights.ranges.30d")}</SelectItem>
              <SelectItem value="90d">{t("insights.ranges.90d")}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      }
    >
      {isLoading ? (
        <Card><CardContent className="p-8 text-sm text-muted-foreground">{t("insights.loading")}</CardContent></Card>
      ) : loadFailed || !dashboard ? (
        <Card><CardContent className="p-8 text-sm text-muted-foreground">{t("insights.loadFailed")}</CardContent></Card>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {summary.map((item) => <SummaryCard key={item.title} title={item.title} value={item.value} hint={item.hint} />)}
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Activity className="size-4 text-primary" />{t("insights.cards.tokenTrend.title")}</CardTitle><CardDescription>{t("insights.cards.tokenTrend.description")}</CardDescription></CardHeader>
              <CardContent>{hasSeriesData(dashboard.token_usage.series) ? <EChart option={seriesOption(dashboard.token_usage.series)} /> : <EmptyChart message={t("insights.noData")} />}</CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><BrainCircuit className="size-4 text-primary" />{t("insights.cards.tokenByOperation.title")}</CardTitle><CardDescription>{t("insights.cards.tokenByOperation.description")}</CardDescription></CardHeader>
              <CardContent>{hasMetricData(dashboard.token_usage.by_operation) ? <EChart option={barOption(dashboard.token_usage.by_operation)} /> : <EmptyChart message={t("insights.noData")} />}</CardContent>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Card>
              <CardHeader><CardTitle className="text-base">{t("insights.cards.providerShare.title")}</CardTitle></CardHeader>
              <CardContent>{hasMetricData(dashboard.token_usage.by_provider) ? <EChart option={metricOption(dashboard.token_usage.by_provider)} height={280} /> : <EmptyChart message={t("insights.noData")} />}</CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">{t("insights.cards.memorySources.title")}</CardTitle></CardHeader>
              <CardContent>{hasMetricData(dashboard.memory.by_source_kind) ? <EChart option={metricOption(dashboard.memory.by_source_kind)} height={280} /> : <EmptyChart message={t("insights.noData")} />}</CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">{t("insights.cards.runtimeDecisions.title")}</CardTitle></CardHeader>
              <CardContent>{hasMetricData(dashboard.runtime.decision_distribution) ? <EChart option={metricOption(dashboard.runtime.decision_distribution)} height={280} /> : <EmptyChart message={t("insights.noData")} />}</CardContent>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Database className="size-4 text-primary" />{t("insights.cards.memoryGrowth.title")}</CardTitle><CardDescription>{t("insights.cards.memoryGrowth.description")}</CardDescription></CardHeader>
              <CardContent>{hasSeriesData(dashboard.memory.growth) ? <EChart option={seriesOption(dashboard.memory.growth, "#16a34a")} /> : <EmptyChart message={t("insights.noData")} />}</CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><TimerReset className="size-4 text-primary" />{t("insights.cards.runtimeThroughput.title")}</CardTitle><CardDescription>{t("insights.cards.runtimeThroughput.description")}</CardDescription></CardHeader>
              <CardContent>{hasSeriesData(dashboard.runtime.request_series) ? <EChart option={seriesOption(dashboard.runtime.request_series, "#ea580c")} /> : <EmptyChart message={t("insights.noData")} />}</CardContent>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="text-base">{t("insights.cards.topCocoonsByMemory.title")}</CardTitle></CardHeader>
              <CardContent>{hasRankedData(dashboard.memory.top_cocoons) ? <EChart option={topCocoonOption(dashboard.memory.top_cocoons)} /> : <EmptyChart message={t("insights.noData")} />}</CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">{t("insights.cards.topCocoonsByErrors.title")}</CardTitle></CardHeader>
              <CardContent>{hasRankedData(dashboard.runtime.top_error_cocoons) ? <EChart option={topCocoonOption(dashboard.runtime.top_error_cocoons)} /> : <EmptyChart message={t("insights.noData")} />}</CardContent>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Card>
              <CardHeader><CardTitle className="text-base">{t("insights.cards.runtimeStatus.title")}</CardTitle></CardHeader>
              <CardContent>{hasMetricData(dashboard.runtime.status_distribution) ? <EChart option={metricOption(dashboard.runtime.status_distribution)} height={280} /> : <EmptyChart message={t("insights.noData")} />}</CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">{t("insights.cards.nodeLatency.title")}</CardTitle></CardHeader>
              <CardContent>{hasMetricData(dashboard.runtime.node_latency) ? <EChart option={barOption(dashboard.runtime.node_latency)} height={280} /> : <EmptyChart message={t("insights.noData")} />}</CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">{t("insights.cards.memoryTypes.title")}</CardTitle></CardHeader>
              <CardContent>{hasMetricData(dashboard.memory.by_memory_type) ? <EChart option={metricOption(dashboard.memory.by_memory_type)} height={280} /> : <EmptyChart message={t("insights.noData")} />}</CardContent>
            </Card>
          </div>
        </div>
      )}
    </PageFrame>
  );
}
