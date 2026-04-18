import { useEffect, useMemo, useState } from "react";
import { Activity, BrainCircuit, Database, TimerReset } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getInsightsOverview, getMemoryInsights, getRuntimeInsights, getTokenUsage } from "@/api/insights";
import type { InsightsOverview, MemoryInsights, NamedMetric, RuntimeInsights, TokenUsageSeries } from "@/api/types";
import AccessCard from "@/components/AccessCard";
import EChart from "@/components/charts/EChart";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useUserStore } from "@/store/useUserStore";

function metricOption(items: NamedMetric[]) {
  return {
    tooltip: { trigger: "item" },
    legend: { bottom: 0 },
    series: [{ type: "pie", radius: ["45%", "70%"], data: items.map((item) => ({ name: item.name, value: item.value })) }],
  };
}

function seriesOption(points: { bucket: string; value: number }[], color = "#2563eb") {
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

function topCocoonOption(items: { cocoon_name: string; value: number }[]) {
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

export default function InsightsPage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const canView = Boolean(userInfo?.can_manage_system);
  const [range, setRange] = useState("30d");
  const [overview, setOverview] = useState<InsightsOverview | null>(null);
  const [tokenUsage, setTokenUsage] = useState<TokenUsageSeries | null>(null);
  const [memoryInsights, setMemoryInsights] = useState<MemoryInsights | null>(null);
  const [runtimeInsights, setRuntimeInsights] = useState<RuntimeInsights | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!canView) return;
    async function loadData() {
      setIsLoading(true);
      try {
        const interval = range === "24h" ? "hour" : "day";
        const [overviewResp, tokenResp, memoryResp, runtimeResp] = await Promise.all([
          getInsightsOverview({ range }),
          getTokenUsage({ range, interval }),
          getMemoryInsights({ range }),
          getRuntimeInsights({ range, interval }),
        ]);
        setOverview(overviewResp);
        setTokenUsage(tokenResp);
        setMemoryInsights(memoryResp);
        setRuntimeInsights(runtimeResp);
      } finally {
        setIsLoading(false);
      }
    }
    void loadData();
  }, [canView, range]);

  const summary = useMemo(() => {
    if (!overview || !runtimeInsights) return null;
    return [
      {
        title: t("insights.summary.totalTokens.title"),
        value: overview.total_tokens.toLocaleString(),
        hint: t("insights.summary.totalTokens.hint"),
      },
      {
        title: t("insights.summary.auditRuns.title"),
        value: overview.total_runs.toLocaleString(),
        hint: t("insights.summary.auditRuns.hint", { value: runtimeInsights.silence_rate }),
      },
      {
        title: t("insights.summary.memories.title"),
        value: memoryInsights?.total_memories.toLocaleString() || "0",
        hint: t("insights.summary.memories.hint"),
      },
      {
        title: t("insights.summary.avgLatency.title"),
        value: `${overview.average_latency_ms} ms`,
        hint: t("insights.summary.avgLatency.hint", { value: runtimeInsights.latency_p95_ms }),
      },
    ];
  }, [memoryInsights, overview, runtimeInsights, t]);

  if (!canView) return <AccessCard description={t("insights.noPermission")} />;

  return (
    <PageFrame
      title={t("insights.title")}
      description={t("insights.description")}
      actions={
        <div className="flex items-center gap-3">
          <Badge variant="outline">{t("insights.sqlBadge")}</Badge>
          <Select value={range} onValueChange={setRange}>
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
      {isLoading || !overview || !tokenUsage || !memoryInsights || !runtimeInsights ? (
        <Card><CardContent className="p-8 text-sm text-muted-foreground">{t("insights.loading")}</CardContent></Card>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {summary?.map((item) => <SummaryCard key={item.title} title={item.title} value={item.value} hint={item.hint} />)}
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Activity className="size-4 text-primary" />{t("insights.cards.tokenTrend.title")}</CardTitle><CardDescription>{t("insights.cards.tokenTrend.description")}</CardDescription></CardHeader>
              <CardContent><EChart option={seriesOption(tokenUsage.series)} /></CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><BrainCircuit className="size-4 text-primary" />{t("insights.cards.tokenByOperation.title")}</CardTitle><CardDescription>{t("insights.cards.tokenByOperation.description")}</CardDescription></CardHeader>
              <CardContent><EChart option={barOption(tokenUsage.by_operation)} /></CardContent>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Card>
              <CardHeader><CardTitle className="text-base">{t("insights.cards.providerShare.title")}</CardTitle></CardHeader>
              <CardContent><EChart option={metricOption(tokenUsage.by_provider)} height={280} /></CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">{t("insights.cards.memorySources.title")}</CardTitle></CardHeader>
              <CardContent><EChart option={metricOption(memoryInsights.by_source_kind)} height={280} /></CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">{t("insights.cards.runtimeDecisions.title")}</CardTitle></CardHeader>
              <CardContent><EChart option={metricOption(runtimeInsights.decision_distribution)} height={280} /></CardContent>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Database className="size-4 text-primary" />{t("insights.cards.memoryGrowth.title")}</CardTitle><CardDescription>{t("insights.cards.memoryGrowth.description")}</CardDescription></CardHeader>
              <CardContent><EChart option={seriesOption(memoryInsights.growth, "#16a34a")} /></CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><TimerReset className="size-4 text-primary" />{t("insights.cards.runtimeThroughput.title")}</CardTitle><CardDescription>{t("insights.cards.runtimeThroughput.description")}</CardDescription></CardHeader>
              <CardContent><EChart option={seriesOption(runtimeInsights.request_series, "#ea580c")} /></CardContent>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="text-base">{t("insights.cards.topCocoonsByMemory.title")}</CardTitle></CardHeader>
              <CardContent><EChart option={topCocoonOption(memoryInsights.top_cocoons)} /></CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">{t("insights.cards.topCocoonsByErrors.title")}</CardTitle></CardHeader>
              <CardContent><EChart option={topCocoonOption(runtimeInsights.top_error_cocoons)} /></CardContent>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Card>
              <CardHeader><CardTitle className="text-base">{t("insights.cards.runtimeStatus.title")}</CardTitle></CardHeader>
              <CardContent><EChart option={metricOption(runtimeInsights.status_distribution)} height={280} /></CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">{t("insights.cards.nodeLatency.title")}</CardTitle></CardHeader>
              <CardContent><EChart option={barOption(runtimeInsights.node_latency)} height={280} /></CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">{t("insights.cards.memoryTypes.title")}</CardTitle></CardHeader>
              <CardContent><EChart option={metricOption(memoryInsights.by_memory_type)} height={280} /></CardContent>
            </Card>
          </div>
        </div>
      )}
    </PageFrame>
  );
}
