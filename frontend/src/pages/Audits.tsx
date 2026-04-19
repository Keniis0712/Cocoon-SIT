import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { Clock3, FileSearch, GitBranch, MessageSquareQuote, ShieldCheck, Sparkles, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { getCocoonAuditRound, listCocoonAuditRounds } from "@/api/audits";
import { getCocoons } from "@/api/cocoons";
import type { AiAuditTraceDetail, AiAuditTraceListItem } from "@/api/types/audit";
import type { CocoonRead } from "@/api/types/cocoons";
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

function humanizeKey(key: string) {
  return key.replace(/_/g, " ");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function SummaryMetric({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }) {
  return <div className="rounded-2xl border border-border/70 p-4 text-sm"><div className="mb-3 flex items-center gap-2 text-muted-foreground">{icon}<span>{label}</span></div><div className="font-medium">{value}</div></div>;
}

export default function AuditsPage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const [searchParams] = useSearchParams();
  const [cocoons, setCocoons] = useState<CocoonRead[]>([]);
  const [selectedCocoonId, setSelectedCocoonId] = useState<string>(searchParams.get("cocoonId") || "");
  const [rounds, setRounds] = useState<AiAuditTraceListItem[]>([]);
  const [selectedRound, setSelectedRound] = useState<AiAuditTraceDetail | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [query, setQuery] = useState("");
  const [roundUid, setRoundUid] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isDetailLoading, setIsDetailLoading] = useState(false);

  const canAudit = Boolean(userInfo?.can_audit);

  useEffect(() => {
    if (!canAudit) return;
    async function loadCocoons() {
      const response = await getCocoons(1, 100);
      setCocoons(response.items);
      if (!selectedCocoonId && response.items[0]) setSelectedCocoonId(String(response.items[0].id));
    }
    void loadCocoons();
  }, [canAudit]);

  useEffect(() => {
    if (!canAudit || !selectedCocoonId) return;
    async function loadRounds() {
      setIsLoading(true);
      try {
        const response = await listCocoonAuditRounds(Number(selectedCocoonId), { page, page_size: 20, q: query || undefined, round_uid: roundUid || undefined });
        setRounds(response.items);
        setTotalPages(response.total_pages || 1);
      } finally {
        setIsLoading(false);
      }
    }
    void loadRounds();
  }, [canAudit, selectedCocoonId, page, query, roundUid]);

  async function openRound(item: AiAuditTraceListItem) {
    setIsDetailLoading(true);
    try {
      const detail = await getCocoonAuditRound(item.cocoon_id, item.id);
      setSelectedRound(detail);
    } finally {
      setIsDetailLoading(false);
    }
  }

  const selectedCocoon = useMemo(() => cocoons.find((item) => String(item.id) === selectedCocoonId) || null, [cocoons, selectedCocoonId]);
  const traceEntries = useMemo(() => (selectedRound?.trace && isRecord(selectedRound.trace) ? Object.entries(selectedRound.trace).filter(([, value]) => value !== undefined) : [] as Array<[string, unknown]>), [selectedRound]);

  function renderTraceValue(value: unknown, depth = 0): ReactNode {
    if (Array.isArray(value)) {
      if (value.length === 0) return <div className="text-sm text-muted-foreground">{t("audits.emptyArray")}</div>;
      return <div className="space-y-2">{value.map((item, index) => <div key={`${depth}-${index}`} className="rounded-xl border border-border/60 bg-background/50 p-3"><div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{t("audits.traceItem", { index: index + 1 })}</div>{renderTraceValue(item, depth + 1)}</div>)}</div>;
    }
    if (isRecord(value)) {
      const entries = Object.entries(value).filter(([, item]) => item !== undefined);
      if (entries.length === 0) return <div className="text-sm text-muted-foreground">{t("audits.emptyFields")}</div>;
      return <div className="grid gap-2">{entries.map(([key, item]) => <div key={`${depth}-${key}`} className="rounded-xl border border-border/60 bg-background/50 p-3"><div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">{humanizeKey(key)}</div>{renderTraceValue(item, depth + 1)}</div>)}</div>;
    }
    if (value === null || value === undefined || value === "") return <span className="text-muted-foreground">-</span>;
    if (typeof value === "boolean") return <Badge variant={value ? "default" : "secondary"}>{String(value)}</Badge>;
    return <span className="whitespace-pre-wrap break-words text-sm leading-6">{String(value)}</span>;
  }

  if (!canAudit) return <AccessCard description={t("audits.noPermission")} />;

  return (
    <PageFrame title={t("audits.title")} description={t("audits.description")} actions={<Badge variant="outline">{selectedCocoon ? t("audits.currentCocoon", { id: selectedCocoon.id }) : t("audits.noCocoon")}</Badge>}>
      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.25fr]">
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2 text-base"><FileSearch className="size-4 text-primary" />{t("audits.filters")}</CardTitle></CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid gap-2"><Label>{t("audits.selectCocoon")}</Label><Select value={selectedCocoonId} onValueChange={(value) => { setSelectedCocoonId(value); setPage(1); setSelectedRound(null); }}><SelectTrigger><SelectValue placeholder={t("audits.selectCocoon")} /></SelectTrigger><SelectContent>{cocoons.map((item) => <SelectItem key={item.id} value={String(item.id)}>{item.name} #{item.id}</SelectItem>)}</SelectContent></Select></div>
              <div className="grid gap-2"><Label>{t("common.keyword")}</Label><Input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder={t("audits.keywordPlaceholder")} /></div>
              <div className="grid gap-2"><Label>{t("audits.roundUid")}</Label><Input value={roundUid} onChange={(event) => { setRoundUid(event.target.value); setPage(1); }} placeholder={t("audits.roundUidPlaceholder")} /></div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">{t("audits.roundsTitle")}</CardTitle><CardDescription>{t("audits.roundsDescription")}</CardDescription></CardHeader>
            <CardContent className="space-y-3">
              {isLoading ? <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("audits.loading")}</div> : rounds.length === 0 ? <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("audits.empty")}</div> : rounds.map((item) => <button key={item.id} type="button" onClick={() => openRound(item)} className="w-full rounded-2xl border border-border/70 p-4 text-left transition hover:border-primary/40 hover:bg-accent/40"><div className="mb-2 flex items-center justify-between gap-3"><div className="font-medium">{item.operation_type}</div><Badge variant={item.status === "success" ? "default" : item.status === "error" ? "destructive" : "secondary"}>{item.status}</Badge></div><div className="text-xs text-muted-foreground">{formatDate(item.created_at)}</div><div className="mt-2 line-clamp-2 text-sm text-muted-foreground">{item.internal_thought || item.user_message?.content || item.assistant_message?.content || item.trigger_event_uid || t("audits.noSummary")}</div></button>)}
              <div className="flex items-center justify-end gap-2"><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>{t("common.previousPage")}</Button><Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>{t("common.nextPage")}</Button></div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader><CardTitle>{t("audits.detailTitle")}</CardTitle><CardDescription>{t("audits.detailDescription")}</CardDescription></CardHeader>
          <CardContent>
            {isDetailLoading ? <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("audits.detailLoading")}</div> : selectedRound ? <div className="space-y-4">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <SummaryMetric icon={<ShieldCheck className="size-4" />} label={t("common.status")} value={<Badge variant={selectedRound.status === "success" ? "default" : selectedRound.status === "error" ? "destructive" : "secondary"}>{selectedRound.status}</Badge>} />
                <SummaryMetric icon={<Sparkles className="size-4" />} label={t("audits.operationType")} value={selectedRound.operation_type} />
                <SummaryMetric icon={<GitBranch className="size-4" />} label={t("audits.decision")} value={selectedRound.decision || "-"} />
                <SummaryMetric icon={<Clock3 className="size-4" />} label={t("audits.roundUid")} value={<span className="break-all">{selectedRound.round_uid}</span>} />
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <Card className="border-border/70 bg-background/40"><CardHeader><CardTitle className="flex items-center gap-2 text-base"><MessageSquareQuote className="size-4 text-primary" />{t("audits.userMessage")}</CardTitle></CardHeader><CardContent className="whitespace-pre-wrap text-sm leading-6">{selectedRound.user_message?.content || selectedRound.trigger_event_uid || "-"}</CardContent></Card>
                <Card className="border-border/70 bg-background/40"><CardHeader><CardTitle className="flex items-center gap-2 text-base"><Sparkles className="size-4 text-primary" />{t("audits.assistantReply")}</CardTitle></CardHeader><CardContent className="whitespace-pre-wrap text-sm leading-6">{selectedRound.assistant_message?.content || "-"}</CardContent></Card>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-2xl border border-border/70 p-4 text-sm"><div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{t("audits.internalThought")}</div><div className="whitespace-pre-wrap leading-6">{selectedRound.internal_thought || "-"}</div></div>
                <div className="rounded-2xl border border-border/70 p-4 text-sm"><div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground"><Clock3 className="size-4" />{t("audits.lifecycle")}</div><div className="space-y-2 text-sm"><div>{t("common.createdAt")}: {formatDate(selectedRound.created_at)}</div><div>{t("audits.startedAt")}: {formatDate(selectedRound.started_at)}</div><div>{t("audits.finishedAt")}: {formatDate(selectedRound.finished_at)}</div></div></div>
              </div>
              {selectedRound.error_detail ? <div className="rounded-2xl border border-destructive/40 bg-destructive/5 p-4 text-sm"><div className="mb-2 flex items-center gap-2 text-destructive"><TriangleAlert className="size-4" />{t("audits.errorDetail")}</div><div className="whitespace-pre-wrap leading-6 text-foreground/90">{selectedRound.error_detail}</div></div> : null}
              <div className="space-y-3"><div className="text-sm font-medium">{t("audits.traceTitle")}</div>{traceEntries.length === 0 ? <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">{t("audits.traceEmpty")}</div> : traceEntries.map(([key, value]) => <Card key={key} className="border-border/70 bg-background/30"><CardHeader><CardTitle className="text-base capitalize">{humanizeKey(key)}</CardTitle></CardHeader><CardContent>{renderTraceValue(value)}</CardContent></Card>)}</div>
            </div> : <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("audits.detailEmpty")}</div>}
          </CardContent>
        </Card>
      </div>
    </PageFrame>
  );
}
