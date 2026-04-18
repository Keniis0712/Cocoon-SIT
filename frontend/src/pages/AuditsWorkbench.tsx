import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
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
import type { AuditArtifactRead, AuditRunDetail, AuditRunListItem, AuditTimelineItem, CocoonRead } from "@/api/types";
import AccessCard from "@/components/AccessCard";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
      <div className="mb-3 flex items-center gap-2 text-muted-foreground">{icon}<span>{label}</span></div>
      <div className="font-medium">{value}</div>
    </div>
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function renderValue(value: unknown, depth = 0): ReactNode {
  if (Array.isArray(value)) {
    if (!value.length) return <span className="text-muted-foreground">[]</span>;
    return (
      <div className="space-y-2">
        {value.map((item, index) => (
          <div key={`${depth}-${index}`} className="rounded-xl border border-border/60 bg-background/60 p-3">
            <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">Item {index + 1}</div>
            {renderValue(item, depth + 1)}
          </div>
        ))}
      </div>
    );
  }
  if (isRecord(value)) {
    const entries = Object.entries(value);
    if (!entries.length) return <span className="text-muted-foreground">{"{}"}</span>;
    return (
      <div className="grid gap-2">
        {entries.map(([key, item]) => (
          <div key={`${depth}-${key}`} className="rounded-xl border border-border/60 bg-background/60 p-3">
            <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{key.replace(/_/g, " ")}</div>
            {renderValue(item, depth + 1)}
          </div>
        ))}
      </div>
    );
  }
  if (value === null || value === undefined || value === "") return <span className="text-muted-foreground">-</span>;
  if (typeof value === "boolean") return <Badge variant={value ? "default" : "secondary"}>{String(value)}</Badge>;
  return <span className="whitespace-pre-wrap break-words text-sm leading-6">{String(value)}</span>;
}

function artifactMap(artifacts: AuditArtifactRead[]) {
  return new Map(artifacts.map((item) => [item.artifact_type, item]));
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
    async function loadCocoons() {
      const response = await getCocoons(1, 100);
      setCocoons(response.items);
    }
    void loadCocoons();
  }, [canAudit]);

  useEffect(() => {
    if (!canAudit) return;
    async function loadRuns() {
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
    }
    void loadRuns();
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
  const artifacts = useMemo(() => artifactMap(selectedRun?.artifacts || []), [selectedRun]);
  const statusLabel = (value: string | null | undefined) => value ? t(`audits.statusValues.${value}`, { defaultValue: value }) : "-";
  const triggerLabel = (value: string | null | undefined) => value ? t(`audits.triggerValues.${value}`, { defaultValue: value }) : "-";
  const decisionLabel = (value: string | null | undefined) => value ? t(`audits.decisionValues.${value}`, { defaultValue: value }) : "-";
  const operationLabel = (value: string | null | undefined) => value ? t(`audits.operationValues.${value}`, { defaultValue: value }) : "-";
  const artifactTitle = (value: string) => t(`audits.artifacts.${value}`, { defaultValue: value });

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
              <CardTitle className="flex items-center gap-2 text-base"><FileSearch className="size-4 text-primary" />{t("audits.filters")}</CardTitle>
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
                    <span>{item.model_name || t("audits.unknownModel")}</span>
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
              <CardTitle className="flex items-center gap-2 text-base"><ListTree className="size-4 text-primary" />{t("audits.timelineTitle")}</CardTitle>
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
                  {[
                    ["input_metadata", "Inputs"],
                    ["meta_result", "Meta Decision"],
                    ["state_after", "State Delta"],
                    ["schedule_after", "Schedule Result"],
                    ["pull_candidates", "Pull Candidates"],
                    ["pull_selected", "Pull Selection"],
                    ["merge_candidates", "Merge Candidates"],
                    ["merge_selected", "Merge Selection"],
                    ["generator_output", "Generator Output"],
                    ["retrieved_memories", "Retrieved Memories"],
                    ["internal_events", "Internal Events"],
                  ].map(([artifactType, title]) => {
                    const artifact = artifacts.get(artifactType);
                    if (!artifact) return null;
                    return (
                      <Card key={artifactType} className="border-border/70 bg-background/30">
                        <CardHeader><CardTitle className="text-base">{artifactTitle(String(artifactType))}</CardTitle></CardHeader>
                        <CardContent>{renderValue(artifact.payload)}</CardContent>
                      </Card>
                    );
                  })}
                </div>

                <Card className="border-border/70 bg-background/30">
                  <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Link2 className="size-4 text-primary" />{t("audits.linksTitle")}</CardTitle></CardHeader>
                  <CardContent className="space-y-3">
                    {selectedRun.links.map((link) => (
                      <div key={link.id} className="rounded-2xl border border-border/70 p-4 text-sm">
                        <div className="font-medium">{link.label || link.link_type}</div>
                        <div className="text-xs text-muted-foreground">{t(`audits.linkTypes.${link.link_type}`, { defaultValue: link.link_type })} · {link.target_uid || link.target_id || "-"}</div>
                      </div>
                    ))}
                    {!selectedRun.links.length ? <div className="text-sm text-muted-foreground">{t("audits.linksEmpty")}</div> : null}
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
