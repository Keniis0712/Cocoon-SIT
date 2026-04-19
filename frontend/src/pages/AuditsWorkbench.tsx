import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ChevronDown,
  Clock3,
  FileSearch,
  GitBranch,
  Link2,
  ListTree,
  MessageSquareQuote,
  ShieldCheck,
  Sparkles,
  TimerReset,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { getAuditRun, getAuditTimeline, listAuditRuns } from "@/api/adminAudits";
import { getCocoons } from "@/api/cocoons";
import type { AuditArtifactRead, AuditRunDetail, AuditRunListItem, AuditStepRead, AuditTimelineItem } from "@/api/types/audit";
import type { CocoonRead } from "@/api/types/cocoons";
import AccessCard from "@/components/AccessCard";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useUserStore } from "@/store/useUserStore";

function formatDate(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "-";
}

function SummaryMetric({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }) {
  return (
    <div className="rounded-2xl border border-border/70 p-4 text-sm">
      <div className="mb-3 flex items-center gap-2 text-muted-foreground">
        {icon}
        <span>{label}</span>
      </div>
      <div className="font-medium">{value}</div>
    </div>
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function humanizeKey(value: string) {
  return value.replace(/_/g, " ");
}

function StructuredValue({
  value,
  label,
  depth = 0,
}: {
  value: unknown;
  label?: string;
  depth?: number;
}) {
  const { t } = useTranslation();
  const triggerLabel = label || t("audits.data");

  if (Array.isArray(value)) {
    if (!value.length) return <span className="text-muted-foreground">[]</span>;
    return (
      <Collapsible className="rounded-xl border border-border/60 bg-background/40">
        <CollapsibleTrigger className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left">
          <div>
            <div className="text-sm font-medium">{triggerLabel}</div>
            <div className="text-xs text-muted-foreground">{t("audits.arrayCount", { count: value.length })}</div>
          </div>
          <ChevronDown className="size-4 text-muted-foreground transition data-[state=open]:rotate-180" />
        </CollapsibleTrigger>
        <CollapsibleContent className="border-t border-border/60 px-4 py-3">
          <div className="space-y-2">
            {value.map((item, index) => (
              <StructuredValue
                key={`${depth}-${index}`}
                value={item}
                label={t("audits.arrayItem", { index: index + 1 })}
                depth={depth + 1}
              />
            ))}
          </div>
        </CollapsibleContent>
      </Collapsible>
    );
  }

  if (isRecord(value)) {
    const entries = Object.entries(value).filter(([, item]) => item !== undefined);
    if (!entries.length) return <span className="text-muted-foreground">{"{}"}</span>;
    return (
      <Collapsible className="rounded-xl border border-border/60 bg-background/40">
        <CollapsibleTrigger className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left">
          <div>
            <div className="text-sm font-medium">{triggerLabel}</div>
            <div className="text-xs text-muted-foreground">{t("audits.fieldCount", { count: entries.length })}</div>
          </div>
          <ChevronDown className="size-4 text-muted-foreground transition data-[state=open]:rotate-180" />
        </CollapsibleTrigger>
        <CollapsibleContent className="border-t border-border/60 px-4 py-3">
          <div className="grid gap-2">
            {entries.map(([key, item]) => (
              <StructuredValue key={`${depth}-${key}`} value={item} label={humanizeKey(key)} depth={depth + 1} />
            ))}
          </div>
        </CollapsibleContent>
      </Collapsible>
    );
  }

  if (value === null || value === undefined || value === "") return <span className="text-muted-foreground">-</span>;
  if (typeof value === "boolean") return <Badge variant={value ? "default" : "secondary"}>{String(value)}</Badge>;
  return <span className="whitespace-pre-wrap break-words text-sm leading-6">{String(value)}</span>;
}

function describeRelationEndpoint(
  link: AuditRunDetail["links"][number],
  artifactsById: Map<string, AuditArtifactRead>,
  stepsById: Map<string, AuditStepRead>,
  stepTitle: (value: string) => string,
  artifactTitle: (value: string) => string,
  side: "source" | "target",
) {
  const artifactId = side === "source" ? link.source_artifact_id : link.target_artifact_id;
  const stepId = side === "source" ? link.source_step_id : link.target_step_id;

  if (artifactId) {
    const artifact = artifactsById.get(artifactId);
    return {
      type: "artifact",
      title: artifact ? artifactTitle(String(artifact.artifact_type)) : artifactTitle("unknown"),
      id: artifactId,
    };
  }
  if (stepId) {
    const step = stepsById.get(stepId);
    return {
      type: "step",
      title: step ? stepTitle(step.step_name) : stepId,
      id: stepId,
    };
  }
  return {
    type: "unknown",
    title: "-",
    id: null,
  };
}

export default function AuditsWorkbenchPage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const canAudit = Boolean(userInfo?.can_audit);
  const [searchParams] = useSearchParams();
  const [cocoons, setCocoons] = useState<CocoonRead[]>([]);
  const [selectedCocoonId, setSelectedCocoonId] = useState<string>(searchParams.get("cocoonId") || "all");
  const [query, setQuery] = useState("");
  const [roundUid, setRoundUid] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [triggerType, setTriggerType] = useState("all");
  const [decision, setDecision] = useState("all");
  const [runs, setRuns] = useState<AuditRunListItem[]>([]);
  const [timeline, setTimeline] = useState<AuditTimelineItem[]>([]);
  const [selectedRun, setSelectedRun] = useState<AuditRunDetail | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [isDetailLoading, setIsDetailLoading] = useState(false);

  useEffect(() => {
    if (!canAudit) return;
    void (async () => {
      const response = await getCocoons(1, 100);
      setCocoons(response.items);
    })();
  }, [canAudit]);

  useEffect(() => {
    if (!canAudit) return;
    void (async () => {
      setIsLoading(true);
      try {
        const cocoonId = selectedCocoonId !== "all" ? Number(selectedCocoonId) : undefined;
        const [runResponse, timelineResponse] = await Promise.all([
          listAuditRuns({
            page,
            page_size: 20,
            cocoon_id: cocoonId,
            q: query || undefined,
            round_uid: roundUid || undefined,
            trigger_type: triggerType !== "all" ? triggerType : undefined,
            status: statusFilter !== "all" ? statusFilter : undefined,
            decision: decision !== "all" ? decision : undefined,
          }),
          getAuditTimeline({ cocoon_id: cocoonId, limit: 20 }),
        ]);
        setRuns(runResponse.items);
        setTotalPages(runResponse.total_pages || 1);
        setTimeline(timelineResponse);
      } finally {
        setIsLoading(false);
      }
    })();
  }, [canAudit, selectedCocoonId, query, roundUid, statusFilter, triggerType, decision, page]);

  async function openRun(item: AuditRunListItem) {
    setIsDetailLoading(true);
    try {
      const detail = await getAuditRun(item.id);
      setSelectedRun(detail);
    } finally {
      setIsDetailLoading(false);
    }
  }

  const selectedCocoon = useMemo(
    () => cocoons.find((item) => String(item.id) === selectedCocoonId) || null,
    [cocoons, selectedCocoonId],
  );
  const statusLabel = (value: string | null | undefined) =>
    value ? t(`audits.statusValues.${value}`, { defaultValue: value }) : "-";
  const triggerLabel = (value: string | null | undefined) =>
    value ? t(`audits.triggerValues.${value}`, { defaultValue: value }) : "-";
  const decisionLabel = (value: string | null | undefined) =>
    value ? t(`audits.decisionValues.${value}`, { defaultValue: value }) : "-";
  const operationLabel = (value: string | null | undefined) =>
    value ? t(`audits.operationValues.${value}`, { defaultValue: value }) : "-";
  const artifactTitle = (value: string) => t(`audits.artifacts.${value}`, { defaultValue: value });
  const stepTitle = (value: string) => t(`audits.stepNames.${value}`, { defaultValue: value });
  const relationTitle = (value: string) => t(`audits.relationTypes.${value}`, { defaultValue: value });

  const artifactsById = useMemo(() => {
    const map = new Map<string, AuditArtifactRead>();
    for (const artifact of selectedRun?.artifacts || []) {
      if (artifact.raw_uid) {
        map.set(artifact.raw_uid, artifact);
      }
    }
    return map;
  }, [selectedRun]);
  const stepsById = useMemo(() => {
    const map = new Map<string, AuditStepRead>();
    for (const step of selectedRun?.steps || []) {
      if (step.raw_uid) {
        map.set(step.raw_uid, step);
      }
    }
    return map;
  }, [selectedRun]);

  if (!canAudit) return <AccessCard description={t("audits.noPermission")} />;

  return (
    <PageFrame
      title={t("audits.title")}
      description={t("audits.description")}
      actions={<Badge variant="outline">{selectedCocoon ? t("audits.currentCocoon", { id: selectedCocoon.id }) : t("audits.allCocoons")}</Badge>}
    >
      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.25fr]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <FileSearch className="size-4 text-primary" />
                {t("audits.filters")}
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid gap-2">
                <Label>{t("audits.selectCocoon")}</Label>
                <Select value={selectedCocoonId} onValueChange={(value) => { setSelectedCocoonId(value); setSelectedRun(null); setPage(1); }}>
                  <SelectTrigger><SelectValue placeholder={t("audits.selectCocoon")} /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t("audits.allCocoons")}</SelectItem>
                    {cocoons.map((item) => <SelectItem key={item.id} value={String(item.id)}>{item.name} #{item.id}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>{t("common.keyword")}</Label>
                <Input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder={t("audits.keywordPlaceholder")} />
              </div>
              <div className="grid gap-2">
                <Label>{t("audits.roundUid")}</Label>
                <Input value={roundUid} onChange={(event) => { setRoundUid(event.target.value); setPage(1); }} placeholder={t("audits.roundUidPlaceholder")} />
              </div>
              <div className="grid gap-2 md:grid-cols-3">
                <div className="grid gap-2">
                  <Label>{t("common.status")}</Label>
                  <Select value={statusFilter} onValueChange={(value) => { setStatusFilter(value); setPage(1); }}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t("common.all")}</SelectItem>
                      <SelectItem value="success">{t("audits.statusValues.success")}</SelectItem>
                      <SelectItem value="silenced">{t("audits.statusValues.silenced")}</SelectItem>
                      <SelectItem value="scheduled">{t("audits.statusValues.scheduled")}</SelectItem>
                      <SelectItem value="error">{t("audits.statusValues.error")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>{t("audits.trigger")}</Label>
                  <Select value={triggerType} onValueChange={(value) => { setTriggerType(value); setPage(1); }}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t("common.all")}</SelectItem>
                      <SelectItem value="user_message">{t("audits.triggerValues.user_message")}</SelectItem>
                      <SelectItem value="wakeup_timer">{t("audits.triggerValues.wakeup_timer")}</SelectItem>
                      <SelectItem value="pull_request">{t("audits.triggerValues.pull_request")}</SelectItem>
                      <SelectItem value="merge_request">{t("audits.triggerValues.merge_request")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>{t("audits.decision")}</Label>
                  <Select value={decision} onValueChange={(value) => { setDecision(value); setPage(1); }}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t("common.all")}</SelectItem>
                      <SelectItem value="reply">{t("audits.decisionValues.reply")}</SelectItem>
                      <SelectItem value="silence">{t("audits.decisionValues.silence")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("audits.runsTitle")}</CardTitle>
              <CardDescription>{t("audits.runsDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {isLoading ? <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("audits.runsLoading")}</div> : null}
              {!isLoading && runs.length === 0 ? <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("audits.empty")}</div> : null}
              {!isLoading ? runs.map((item) => (
                <button key={item.id} type="button" onClick={() => openRun(item)} className="w-full rounded-2xl border border-border/70 p-4 text-left transition hover:border-primary/40 hover:bg-accent/40">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <div className="font-medium">{operationLabel(item.operation_type)}</div>
                    <Badge variant={item.status === "error" ? "destructive" : item.status === "success" ? "default" : "secondary"}>{statusLabel(item.status)}</Badge>
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                    <span>{triggerLabel(item.trigger_type)}</span>
                    {item.model_name ? <span>{item.model_name}</span> : null}
                    <span>{formatDate(item.created_at)}</span>
                  </div>
                  <div className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                    {item.internal_thought || item.user_message?.content || item.assistant_message?.content || item.round_uid || t("audits.noSummary")}
                  </div>
                </button>
              )) : null}
              <div className="flex items-center justify-end gap-2">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>{t("common.previousPage")}</Button>
                <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>{t("common.nextPage")}</Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <ListTree className="size-4 text-primary" />
                {t("audits.timelineTitle")}
              </CardTitle>
              <CardDescription>{t("audits.timelineDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {timeline.map((item) => (
                <div key={`${item.kind}-${item.target_uid || item.target_id || item.occurred_at}`} className="rounded-2xl border border-border/70 p-4">
                  <div className="mb-1 flex items-center justify-between gap-3">
                    <div className="font-medium">{item.label}</div>
                    <Badge variant="outline">{t(`audits.timelineKinds.${item.kind}`, { defaultValue: item.kind })}</Badge>
                  </div>
                  <div className="text-xs text-muted-foreground">{formatDate(item.occurred_at)}{item.status ? ` · ${statusLabel(item.status)}` : ""}</div>
                </div>
              ))}
              {!timeline.length ? <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("audits.timelineEmpty")}</div> : null}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{t("audits.detailTitle")}</CardTitle>
            <CardDescription>{t("audits.detailDescription")}</CardDescription>
          </CardHeader>
          <CardContent>
            {isDetailLoading ? <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("audits.detailLoading")}</div> : null}
            {!isDetailLoading && !selectedRun ? <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("audits.detailEmpty")}</div> : null}
            {!isDetailLoading && selectedRun ? (
              <div className="space-y-4">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <SummaryMetric icon={<ShieldCheck className="size-4" />} label={t("common.status")} value={<Badge variant={selectedRun.status === "error" ? "destructive" : selectedRun.status === "success" ? "default" : "secondary"}>{statusLabel(selectedRun.status)}</Badge>} />
                  <SummaryMetric icon={<GitBranch className="size-4" />} label={t("audits.decision")} value={decisionLabel(selectedRun.decision)} />
                  <SummaryMetric icon={<Sparkles className="size-4" />} label={t("common.model")} value={selectedRun.model_name || "-"} />
                  <SummaryMetric icon={<Clock3 className="size-4" />} label={t("audits.latency")} value={selectedRun.latency_ms ? `${selectedRun.latency_ms.toFixed(0)} ms` : "-"} />
                </div>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <SummaryMetric icon={<Activity className="size-4" />} label={t("audits.tokens")} value={selectedRun.token_total ?? "-"} />
                  <SummaryMetric icon={<TimerReset className="size-4" />} label={t("audits.schedule")} value={selectedRun.schedule_action || "-"} />
                  <SummaryMetric icon={<MessageSquareQuote className="size-4" />} label={t("audits.trigger")} value={triggerLabel(selectedRun.trigger_type)} />
                  <SummaryMetric icon={<Sparkles className="size-4" />} label={t("audits.roundUid")} value={<span className="break-all">{selectedRun.round_uid}</span>} />
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <Card className="border-border/70 bg-background/40">
                    <CardHeader><CardTitle className="text-base">{t("audits.userTriggerInput")}</CardTitle></CardHeader>
                    <CardContent className="whitespace-pre-wrap text-sm leading-6">
                      {selectedRun.user_message?.content || selectedRun.trigger_event_uid || "-"}
                    </CardContent>
                  </Card>
                  <Card className="border-border/70 bg-background/40">
                    <CardHeader><CardTitle className="text-base">{t("audits.assistantOutput")}</CardTitle></CardHeader>
                    <CardContent className="whitespace-pre-wrap text-sm leading-6">{selectedRun.assistant_message?.content || "-"}</CardContent>
                  </Card>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-2xl border border-border/70 p-4 text-sm">
                    <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{t("audits.internalThought")}</div>
                    <div className="whitespace-pre-wrap leading-6">{selectedRun.internal_thought || "-"}</div>
                  </div>
                  <div className="rounded-2xl border border-border/70 p-4 text-sm">
                    <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{t("audits.lifecycle")}</div>
                    <div className="space-y-2">
                      <div>{t("common.createdAt")}: {formatDate(selectedRun.created_at)}</div>
                      <div>{t("audits.startedAt")}: {formatDate(selectedRun.started_at)}</div>
                      <div>{t("audits.finishedAt")}: {formatDate(selectedRun.finished_at)}</div>
                      <div>{t("audits.wakeupAt")}: {formatDate(selectedRun.scheduled_wakeup_at)}</div>
                    </div>
                  </div>
                </div>

                <Card className="border-border/70 bg-background/30">
                  <CardHeader><CardTitle className="text-base">{t("audits.stepsTitle")}</CardTitle></CardHeader>
                  <CardContent className="space-y-3">
                    {selectedRun.steps.map((step) => (
                      <div key={step.id} className="rounded-2xl border border-border/70 p-4">
                        <div className="mb-1 flex items-center justify-between gap-3">
                          <div className="font-medium">{t(`audits.stepNames.${step.step_name}`, { defaultValue: step.step_name })}</div>
                          <Badge variant={step.status === "error" ? "destructive" : "secondary"}>{statusLabel(step.status)}</Badge>
                        </div>
                        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                          <span>{t("audits.latency")}: {step.latency_ms ? `${step.latency_ms.toFixed(0)} ms` : "-"}</span>
                          <span>{t("audits.tokens")}: {step.token_total ?? "-"}</span>
                        </div>
                        {step.error_detail ? <div className="mt-2 text-sm text-destructive">{step.error_detail}</div> : null}
                      </div>
                    ))}
                    {!selectedRun.steps.length ? <div className="text-sm text-muted-foreground">{t("audits.stepsEmpty")}</div> : null}
                  </CardContent>
                </Card>

                <div className="grid gap-3">
                  {selectedRun.artifacts.map((artifact) => (
                    <Collapsible key={`${artifact.artifact_type}-${artifact.id}`} className="rounded-xl border border-border/70 bg-background/30">
                      <CollapsibleTrigger className="flex w-full items-center justify-between gap-3 px-6 py-4 text-left">
                        <div>
                          <div className="text-base font-semibold">{artifactTitle(String(artifact.artifact_type))}</div>
                          {artifact.title ? <div className="mt-1 text-sm text-muted-foreground">{artifact.title}</div> : null}
                        </div>
                        <ChevronDown className="size-4 text-muted-foreground transition data-[state=open]:rotate-180" />
                      </CollapsibleTrigger>
                      <CollapsibleContent className="border-t border-border/70 px-6 py-4">
                        <StructuredValue value={artifact.payload} label={artifactTitle(String(artifact.artifact_type))} />
                      </CollapsibleContent>
                    </Collapsible>
                  ))}
                  {!selectedRun.artifacts.length ? <div className="text-sm text-muted-foreground">{t("audits.traceEmpty")}</div> : null}
                </div>

                <Card className="border-border/70 bg-background/30">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Link2 className="size-4 text-primary" />
                      {t("audits.relationsTitle")}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {selectedRun.links.map((link) => {
                      const source = describeRelationEndpoint(link, artifactsById, stepsById, stepTitle, artifactTitle, "source");
                      const target = describeRelationEndpoint(link, artifactsById, stepsById, stepTitle, artifactTitle, "target");
                      return (
                        <Collapsible key={link.id} className="rounded-2xl border border-border/70">
                          <CollapsibleTrigger className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left">
                            <div>
                              <div className="font-medium">{relationTitle(link.relation)}</div>
                              <div className="mt-1 text-xs text-muted-foreground">
                                {source.title} → {target.title}
                              </div>
                            </div>
                            <ChevronDown className="size-4 text-muted-foreground transition data-[state=open]:rotate-180" />
                          </CollapsibleTrigger>
                          <CollapsibleContent className="border-t border-border/70 px-4 py-3 text-sm">
                            <div className="grid gap-3 md:grid-cols-2">
                              <div className="rounded-xl border border-border/60 bg-background/50 p-3">
                                <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("audits.relationSource")}</div>
                                <div className="mt-2 font-medium">{source.title}</div>
                                <div className="mt-1 text-xs text-muted-foreground">{source.id || "-"}</div>
                              </div>
                              <div className="rounded-xl border border-border/60 bg-background/50 p-3">
                                <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("audits.relationTarget")}</div>
                                <div className="mt-2 font-medium">{target.title}</div>
                                <div className="mt-1 text-xs text-muted-foreground">{target.id || "-"}</div>
                              </div>
                            </div>
                          </CollapsibleContent>
                        </Collapsible>
                      );
                    })}
                    {!selectedRun.links.length ? <div className="text-sm text-muted-foreground">{t("audits.relationsEmpty")}</div> : null}
                  </CardContent>
                </Card>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </PageFrame>
  );
}
