import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { GitMerge, Layers3, RefreshCcw, ShieldCheck, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { getCocoons } from "@/api/cocoons";
import { createMergeJob, getMergeJobDetail, listMergeJobs } from "@/api/merges";
import type { CocoonRead } from "@/api/types/cocoons";
import type { CocoonMergeCreatePayload, CocoonMergeJobDetail, CocoonMergeJobRead } from "@/api/types/operations";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useUserStore } from "@/store/useUserStore";

type MergeFormState = {
  source_cocoon_id: string;
  target_cocoon_id: string;
  strategy: CocoonMergeCreatePayload["strategy"];
  include_dialogues: boolean;
  dialogue_strategy: CocoonMergeCreatePayload["dialogue_strategy"];
  max_dialogue_items: string;
  max_result_items: string;
};

const STATUS_ALL = "__all";

function formatDate(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "-";
}

function humanizeKey(key: string) {
  return key.replace(/_/g, " ");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function SummaryMetric({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }) {
  return <div className="rounded-2xl border border-border/70 p-4 text-sm"><div className="mb-3 flex items-center gap-2 text-muted-foreground">{icon}<span>{label}</span></div><div className="font-medium">{value}</div></div>;
}

export default function MergesPage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const [searchParams] = useSearchParams();
  const [cocoons, setCocoons] = useState<CocoonRead[]>([]);
  const [jobs, setJobs] = useState<CocoonMergeJobRead[]>([]);
  const [selectedJob, setSelectedJob] = useState<CocoonMergeJobDetail | null>(null);
  const [form, setForm] = useState<MergeFormState>({
    source_cocoon_id: searchParams.get("sourceCocoonId") || "",
    target_cocoon_id: searchParams.get("targetCocoonId") || "",
    strategy: "subtle",
    include_dialogues: true,
    dialogue_strategy: "balanced",
    max_dialogue_items: "120",
    max_result_items: "30",
  });
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [statusFilter, setStatusFilter] = useState(STATUS_ALL);
  const [mergeUid, setMergeUid] = useState("");
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isDetailLoading, setIsDetailLoading] = useState(false);

  const cocoonMap = useMemo(() => {
    const map = new Map<number, CocoonRead>();
    for (const cocoon of cocoons) {
      map.set(cocoon.id, cocoon);
    }
    return map;
  }, [cocoons]);

  useEffect(() => {
    void loadCocoons();
  }, [userInfo?.can_manage_system]);

  useEffect(() => {
    void loadJobs();
  }, [page, statusFilter, mergeUid, query]);

  async function loadCocoons() {
    try {
      const items: CocoonRead[] = [];
      let currentPage = 1;
      let total = 1;
      do {
        const response = await getCocoons(currentPage, 100, userInfo?.can_manage_system ? "all" : "mine");
        items.push(...response.items);
        total = response.total_pages || 1;
        currentPage += 1;
      } while (currentPage <= total);
      setCocoons(items);
    } catch {
      toast.error(t("merges.loadCocoonsFailed"));
    }
  }

  async function loadJobs() {
    setIsLoading(true);
    try {
      const response = await listMergeJobs(page, 20, {
        scope: userInfo?.can_manage_system ? "all" : "mine",
        status: statusFilter === STATUS_ALL ? undefined : statusFilter,
        merge_uid: mergeUid.trim() || undefined,
        q: query.trim() || undefined,
      });
      setJobs(response.items);
      setTotalPages(response.total_pages || 1);
    } catch {
      toast.error(t("merges.loadJobsFailed"));
    } finally {
      setIsLoading(false);
    }
  }

  async function openJob(job: CocoonMergeJobRead) {
    setIsDetailLoading(true);
    try {
      const detail = await getMergeJobDetail(job.merge_uid);
      setSelectedJob(detail);
    } catch {
      toast.error(t("merges.loadDetailFailed"));
    } finally {
      setIsDetailLoading(false);
    }
  }

  function isAncestorOrSelf(sourceId: number, targetId: number) {
    const visited = new Set<number>();
    let current: number | null = sourceId;
    while (current && !visited.has(current)) {
      visited.add(current);
      if (current === targetId) {
        return true;
      }
      current = cocoonMap.get(current)?.parent_id ?? null;
    }
    return false;
  }

  async function submitMerge() {
    const sourceId = Number(form.source_cocoon_id);
    const targetId = Number(form.target_cocoon_id);
    if (!sourceId || !targetId) {
      toast.error(t("merges.selectSourceTarget"));
      return;
    }
    if (sourceId === targetId) {
      toast.error(t("merges.sameSourceTarget"));
      return;
    }
    if (!isAncestorOrSelf(sourceId, targetId)) {
      toast.error(t("merges.invalidLineage"));
      return;
    }

    setIsSaving(true);
    try {
      const job = await createMergeJob({
        source_cocoon_id: sourceId,
        target_cocoon_id: targetId,
        strategy: form.strategy,
        include_dialogues: form.include_dialogues,
        dialogue_strategy: form.dialogue_strategy,
        max_dialogue_items: Number(form.max_dialogue_items || "120"),
        max_result_items: Number(form.max_result_items || "30"),
      });
      toast.success(t("merges.created"));
      await loadJobs();
      await openJob(job);
    } catch {
      toast.error(t("merges.createFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  const traceEntries = useMemo(
    () => (selectedJob?.trace && isRecord(selectedJob.trace) ? Object.entries(selectedJob.trace).filter(([, value]) => value !== undefined) : []),
    [selectedJob],
  );

  function renderTraceValue(value: unknown, depth = 0): ReactNode {
    if (Array.isArray(value)) {
      if (value.length === 0) return <div className="text-sm text-muted-foreground">{t("merges.emptyArray")}</div>;
      return <div className="space-y-2">{value.map((item, index) => <div key={`${depth}-${index}`} className="rounded-xl border border-border/60 bg-background/50 p-3"><div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{t("merges.traceItem", { index: index + 1 })}</div>{renderTraceValue(item, depth + 1)}</div>)}</div>;
    }
    if (isRecord(value)) {
      const entries = Object.entries(value).filter(([, item]) => item !== undefined);
      if (entries.length === 0) return <div className="text-sm text-muted-foreground">{t("merges.emptyFields")}</div>;
      return <div className="grid gap-2">{entries.map(([key, item]) => <div key={`${depth}-${key}`} className="rounded-xl border border-border/60 bg-background/50 p-3"><div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">{humanizeKey(key)}</div>{renderTraceValue(item, depth + 1)}</div>)}</div>;
    }
    if (value === null || value === undefined || value === "") return <span className="text-muted-foreground">-</span>;
    if (typeof value === "boolean") return <Badge variant={value ? "default" : "secondary"}>{String(value)}</Badge>;
    return <span className="whitespace-pre-wrap break-words text-sm leading-6">{String(value)}</span>;
  }

  return (
    <PageFrame
      title={t("merges.title")}
      description={t("merges.description")}
      actions={
        <Button variant="outline" onClick={() => void loadJobs()}>
          <RefreshCcw className="mr-2 size-4" />
          {t("common.refresh")}
        </Button>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.25fr]">
        <div className="space-y-4">
          <Card className="border-border/70 bg-card/90">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <GitMerge className="size-4 text-primary" />
                {t("merges.createTitle")}
              </CardTitle>
              <CardDescription>{t("merges.createDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-2">
                  <Label>{t("merges.sourceCocoon")}</Label>
                  <Select value={form.source_cocoon_id} onValueChange={(value) => setForm((prev) => ({ ...prev, source_cocoon_id: value }))}>
                    <SelectTrigger><SelectValue placeholder={t("merges.selectCocoon")} /></SelectTrigger>
                    <SelectContent>
                      {cocoons.map((cocoon) => (
                        <SelectItem key={cocoon.id} value={String(cocoon.id)}>
                          {cocoon.name} #{cocoon.id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>{t("merges.targetCocoon")}</Label>
                  <Select value={form.target_cocoon_id} onValueChange={(value) => setForm((prev) => ({ ...prev, target_cocoon_id: value }))}>
                    <SelectTrigger><SelectValue placeholder={t("merges.selectCocoon")} /></SelectTrigger>
                    <SelectContent>
                      {cocoons.map((cocoon) => (
                        <SelectItem key={cocoon.id} value={String(cocoon.id)}>
                          {cocoon.name} #{cocoon.id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-2">
                  <Label>{t("merges.strategy")}</Label>
                  <Select value={form.strategy} onValueChange={(value) => setForm((prev) => ({ ...prev, strategy: value as MergeFormState["strategy"] }))}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="archive">archive</SelectItem>
                      <SelectItem value="subtle">subtle</SelectItem>
                      <SelectItem value="overhaul">overhaul</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>{t("merges.dialogueStrategy")}</Label>
                  <Select value={form.dialogue_strategy} onValueChange={(value) => setForm((prev) => ({ ...prev, dialogue_strategy: value as MergeFormState["dialogue_strategy"] }))}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="recent_only">recent_only</SelectItem>
                      <SelectItem value="balanced">balanced</SelectItem>
                      <SelectItem value="all">all</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
                <Checkbox checked={form.include_dialogues} onCheckedChange={(checked) => setForm((prev) => ({ ...prev, include_dialogues: Boolean(checked) }))} />
                <span>{t("merges.includeDialogues")}</span>
              </label>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-2">
                  <Label>{t("merges.maxDialogueItems")}</Label>
                  <Input type="number" min="0" value={form.max_dialogue_items} onChange={(event) => setForm((prev) => ({ ...prev, max_dialogue_items: event.target.value }))} />
                </div>
                <div className="grid gap-2">
                  <Label>{t("merges.maxResultItems")}</Label>
                  <Input type="number" min="1" value={form.max_result_items} onChange={(event) => setForm((prev) => ({ ...prev, max_result_items: event.target.value }))} />
                </div>
              </div>
              <Button disabled={isSaving} onClick={() => void submitMerge()}>
                <Sparkles className="mr-2 size-4" />
                {isSaving ? t("common.saving") : t("merges.createJob")}
              </Button>
            </CardContent>
          </Card>

          <Card className="border-border/70 bg-card/90">
            <CardHeader>
              <CardTitle className="text-base">{t("merges.listTitle")}</CardTitle>
              <CardDescription>{t("merges.listDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 md:grid-cols-3">
                <div className="grid gap-2">
                  <Label>{t("common.status")}</Label>
                  <Select value={statusFilter} onValueChange={(value) => { setStatusFilter(value); setPage(1); }}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value={STATUS_ALL}>{t("merges.statusAll")}</SelectItem>
                      <SelectItem value="pending">pending</SelectItem>
                      <SelectItem value="running">running</SelectItem>
                      <SelectItem value="success">success</SelectItem>
                      <SelectItem value="error">error</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>{t("merges.mergeUid")}</Label>
                  <Input value={mergeUid} onChange={(event) => { setMergeUid(event.target.value); setPage(1); }} placeholder={t("merges.mergeUidPlaceholder")} />
                </div>
                <div className="grid gap-2">
                  <Label>{t("common.keyword")}</Label>
                  <Input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder={t("merges.keywordPlaceholder")} />
                </div>
              </div>
              {isLoading ? (
                <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("common.loading")}</div>
              ) : jobs.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("merges.empty")}</div>
              ) : (
                jobs.map((job) => (
                  <button key={job.merge_uid} type="button" onClick={() => void openJob(job)} className="w-full rounded-2xl border border-border/70 p-4 text-left transition hover:border-primary/40 hover:bg-accent/40">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <div className="font-medium">{job.merge_uid}</div>
                      <Badge variant={job.status === "success" ? "default" : job.status === "error" ? "destructive" : "secondary"}>{job.status}</Badge>
                    </div>
                    <div className="text-xs text-muted-foreground">{t("merges.lineage", { source: job.source_cocoon_id, target: job.target_cocoon_id })}</div>
                    <div className="mt-2 text-xs text-muted-foreground">{formatDate(job.created_at)}</div>
                  </button>
                ))
              )}
              <div className="flex items-center justify-end gap-2">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>{t("common.previousPage")}</Button>
                <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>{t("common.nextPage")}</Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle>{t("merges.detailTitle")}</CardTitle>
            <CardDescription>{t("merges.detailDescription")}</CardDescription>
          </CardHeader>
          <CardContent>
            {isDetailLoading ? (
              <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("merges.detailLoading")}</div>
            ) : selectedJob ? (
              <div className="space-y-4">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <SummaryMetric icon={<ShieldCheck className="size-4" />} label={t("common.status")} value={<Badge variant={selectedJob.status === "success" ? "default" : selectedJob.status === "error" ? "destructive" : "secondary"}>{selectedJob.status}</Badge>} />
                  <SummaryMetric icon={<GitMerge className="size-4" />} label={t("merges.strategy")} value={selectedJob.strategy} />
                  <SummaryMetric icon={<Layers3 className="size-4" />} label={t("merges.candidateCount")} value={selectedJob.candidate_count} />
                  <SummaryMetric icon={<Sparkles className="size-4" />} label={t("merges.mergedCount")} value={selectedJob.merged_count} />
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-2xl border border-border/70 p-4 text-sm">
                    <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{t("merges.inputParams")}</div>
                    <div className="space-y-2">
                      <div>{t("merges.lineage", { source: selectedJob.source_cocoon_id, target: selectedJob.target_cocoon_id })}</div>
                      <div>{t("merges.mergeUid")}: <span className="break-all">{selectedJob.merge_uid}</span></div>
                      <div>{t("merges.strategy")}: {selectedJob.strategy}</div>
                    </div>
                  </div>
                  <div className="rounded-2xl border border-border/70 p-4 text-sm">
                    <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{t("merges.lifecycle")}</div>
                    <div className="space-y-2">
                      <div>{t("common.createdAt")}: {formatDate(selectedJob.created_at)}</div>
                      <div>{t("merges.startedAt")}: {formatDate(selectedJob.started_at)}</div>
                      <div>{t("merges.finishedAt")}: {formatDate(selectedJob.finished_at)}</div>
                    </div>
                  </div>
                </div>
                <div className="space-y-3">
                  <div className="text-sm font-medium">{t("merges.traceTitle")}</div>
                  {traceEntries.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">{t("merges.traceEmpty")}</div>
                  ) : (
                    traceEntries.map(([key, value]) => (
                      <Card key={key} className="border-border/70 bg-background/30">
                        <CardHeader><CardTitle className="text-base capitalize">{humanizeKey(key)}</CardTitle></CardHeader>
                        <CardContent>{renderTraceValue(value)}</CardContent>
                      </Card>
                    ))
                  )}
                </div>
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("merges.detailEmpty")}</div>
            )}
          </CardContent>
        </Card>
      </div>
    </PageFrame>
  );
}
