import { useEffect, useState } from "react";
import { ArrowLeft, BrainCircuit, Pencil, Sparkles, Tags, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { showErrorToast } from "@/api/client";
import {
  deleteCocoonMemory,
  getCocoon,
  getCocoonMemories,
  reorganizeCocoonMemories,
  updateCocoonMemory,
} from "@/api/cocoons";
import type { CocoonRead, MemoryChunkRead, MemoryOverviewRead } from "@/api/types/cocoons";
import { useConfirmDialog } from "@/components/composes/useConfirmDialog";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

function formatTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "-";
}

function parseTagsInput(value: string) {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildOverview(items: MemoryChunkRead[]): MemoryOverviewRead {
  const byPool: Record<string, number> = {};
  const byType: Record<string, number> = {};
  const byStatus: Record<string, number> = {};
  const tagCounts = new Map<string, number>();
  let importanceTotal = 0;
  let confidenceTotal = 0;

  for (const item of items) {
    byPool[item.memory_pool] = (byPool[item.memory_pool] || 0) + 1;
    byType[item.memory_type] = (byType[item.memory_type] || 0) + 1;
    byStatus[item.status] = (byStatus[item.status] || 0) + 1;
    importanceTotal += item.importance || 0;
    confidenceTotal += item.confidence || 0;
    for (const tag of item.tags || []) {
      tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1);
    }
  }

  return {
    total: items.length,
    by_pool: byPool,
    by_type: byType,
    by_status: byStatus,
    tag_cloud: Array.from(tagCounts.entries())
      .map(([tag, count]) => ({ tag, count }))
      .sort((left, right) => right.count - left.count || left.tag.localeCompare(right.tag))
      .slice(0, 24),
    importance_average: items.length ? Number((importanceTotal / items.length).toFixed(2)) : 0,
    confidence_average: items.length ? Number((confidenceTotal / items.length).toFixed(2)) : 0,
  };
}

function OverviewCloud({ overview, emptyLabel }: { overview: MemoryOverviewRead | null; emptyLabel: string }) {
  const tags = overview?.tag_cloud || [];
  const maxCount = tags.length ? Math.max(...tags.map((item) => item.count)) : 1;

  return (
    <div className="flex flex-wrap gap-3">
      {tags.length ? tags.map((item) => {
        const scale = 0.9 + (item.count / maxCount) * 0.7;
        return (
          <span
            key={item.tag}
            className="rounded-full border border-border/60 bg-background/70 px-3 py-2 font-medium text-foreground/90"
            style={{ fontSize: `${scale}rem` }}
          >
            {item.tag}
          </span>
        );
      }) : <div className="text-sm text-muted-foreground">{emptyLabel}</div>}
    </div>
  );
}

export default function CocoonMemoryPage() {
  const { t } = useTranslation("workspace");
  const navigate = useNavigate();
  const params = useParams();
  const cocoonId = Number(params.cocoonId);

  const [cocoon, setCocoon] = useState<CocoonRead | null>(null);
  const [items, setItems] = useState<MemoryChunkRead[]>([]);
  const [overview, setOverview] = useState<MemoryOverviewRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [editing, setEditing] = useState<MemoryChunkRead | null>(null);
  const [editContent, setEditContent] = useState("");
  const [editSummary, setEditSummary] = useState("");
  const [editTags, setEditTags] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isReorganizeOpen, setIsReorganizeOpen] = useState(false);
  const [reorganizeInstructions, setReorganizeInstructions] = useState("");
  const [isReorganizing, setIsReorganizing] = useState(false);
  const { confirm, confirmDialog } = useConfirmDialog();

  useEffect(() => {
    if (!Number.isFinite(cocoonId) || cocoonId <= 0) {
      navigate("/cocoons", { replace: true });
      return;
    }
    void load();
  }, [cocoonId]);

  useEffect(() => {
    if (!editing) {
      setEditContent("");
      setEditSummary("");
      setEditTags("");
      return;
    }
    setEditContent(editing.content || "");
    setEditSummary(editing.summary || "");
    setEditTags((editing.tags || []).join(", "));
  }, [editing]);

  async function load() {
    setIsLoading(true);
    try {
      const [cocoonResp, memoryResp] = await Promise.all([
        getCocoon(cocoonId),
        getCocoonMemories(cocoonId),
      ]);
      setCocoon(cocoonResp);
      setItems(memoryResp.items);
      setOverview(memoryResp.overview);
      setSelectedIds((prev) => prev.filter((id) => memoryResp.items.some((item) => item.id === id)));
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("memoryLoadFailed", { defaultValue: "Failed to load memory." }));
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDeleteMemory(memory: MemoryChunkRead) {
    const accepted = await confirm({
      title: t("deleteMemory", { defaultValue: "Delete memory" }),
      description: t("deleteMemoryConfirm", { id: memory.id, defaultValue: `Delete memory #${memory.id}?` }),
      confirmLabel: t("deleteMemory", { defaultValue: "Delete memory" }),
      cancelLabel: t("common.cancel", { defaultValue: "Cancel" }),
      variant: "destructive",
    });
    if (!accepted) {
      return;
    }
    try {
      await deleteCocoonMemory(cocoonId, memory.id);
      const nextItems = items.filter((item) => item.id !== memory.id);
      setItems(nextItems);
      setOverview(buildOverview(nextItems));
      setSelectedIds((prev) => prev.filter((id) => id !== memory.id));
      toast.success(t("memoryDeleted", { defaultValue: "Memory deleted." }));
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("memoryDeleteFailed", { defaultValue: "Failed to delete memory." }));
    }
  }

  async function handleSaveEdit() {
    if (!editing) return;
    setIsSaving(true);
    try {
      await updateCocoonMemory(cocoonId, editing.id, {
        content: editContent,
        summary: editSummary || null,
        tags_json: parseTagsInput(editTags),
      });
      setEditing(null);
      await load();
      toast.success(t("memorySaved", { defaultValue: "Memory updated." }));
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("memorySaveFailed", { defaultValue: "Failed to save memory." }));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleReorganize() {
    if (!selectedIds.length) return;
    setIsReorganizing(true);
    try {
      const job = await reorganizeCocoonMemories(cocoonId, {
        memory_ids: selectedIds,
        instructions: reorganizeInstructions.trim() || undefined,
      }) as { status?: string };
      setIsReorganizeOpen(false);
      setReorganizeInstructions("");
      toast.success(t("memoryReorganizeQueued", { defaultValue: `Reorganization queued (${job.status}).` }));
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("memoryReorganizeFailed", { defaultValue: "Failed to queue memory reorganization." }));
    } finally {
      setIsReorganizing(false);
    }
  }

  const selectedCount = selectedIds.length;
  const byPool = Object.entries(overview?.by_pool || {});
  const byType = Object.entries(overview?.by_type || {});
  const byStatus = Object.entries(overview?.by_status || {});

  return (
    <PageFrame
      title={t("memoryPageTitle", { name: cocoon?.name || "Cocoon", defaultValue: `${cocoon?.name || "Cocoon"} Memory` })}
      description={t("memoryPageDescription", { defaultValue: "Review, edit, and reorganize the cocoon's memory set." })}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={() => navigate(`/cocoons/${cocoonId}`)}>
            <ArrowLeft className="mr-2 size-4" />
            {t("backToChat", { defaultValue: "Back to chat" })}
          </Button>
          <Button variant="outline" disabled={!selectedCount} onClick={() => setIsReorganizeOpen(true)}>
            <Sparkles className="mr-2 size-4" />
            {t("memoryReorganize", { defaultValue: "AI reorganize" })}
          </Button>
        </div>
      }
    >
      <div className="space-y-6">
        <Card className="border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BrainCircuit className="size-4 text-primary" />
              {t("memoryOverview", { defaultValue: "Memory overview" })}
            </CardTitle>
            <CardDescription>{t("memoryOverviewDescription", { defaultValue: "A quick view of what this cocoon can currently remember." })}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-2xl border border-border/70 p-4">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("common.total", { defaultValue: "Total" })}</div>
                <div className="mt-2 text-3xl font-semibold">{overview?.total ?? 0}</div>
              </div>
              <div className="rounded-2xl border border-border/70 p-4">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("memoryAvgImportance", { defaultValue: "Avg importance" })}</div>
                <div className="mt-2 text-3xl font-semibold">{overview?.importance_average ?? 0}</div>
              </div>
              <div className="rounded-2xl border border-border/70 p-4">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("memoryAvgConfidence", { defaultValue: "Avg confidence" })}</div>
                <div className="mt-2 text-3xl font-semibold">{overview?.confidence_average ?? 0}</div>
              </div>
              <div className="rounded-2xl border border-border/70 p-4">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("memorySelected", { defaultValue: "Selected" })}</div>
                <div className="mt-2 text-3xl font-semibold">{selectedCount}</div>
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
              <div className="rounded-2xl border border-border/70 p-4">
                <div className="mb-3 flex items-center gap-2 text-sm font-medium">
                  <Tags className="size-4 text-primary" />
                  {t("memoryTagCloud", { defaultValue: "Tag cloud" })}
                </div>
                <OverviewCloud overview={overview} emptyLabel={t("memoryNoTagsYet", { defaultValue: "No tags yet." })} />
              </div>
              <div className="grid gap-4">
                <div className="rounded-2xl border border-border/70 p-4">
                  <div className="mb-2 text-sm font-medium">{t("memoryByPool", { defaultValue: "By pool" })}</div>
                  <div className="flex flex-wrap gap-2">
                    {byPool.length ? byPool.map(([key, count]) => <Badge key={key} variant="outline">{key}: {count}</Badge>) : <span className="text-sm text-muted-foreground">-</span>}
                  </div>
                </div>
                <div className="rounded-2xl border border-border/70 p-4">
                  <div className="mb-2 text-sm font-medium">{t("memoryByType", { defaultValue: "By type" })}</div>
                  <div className="flex flex-wrap gap-2">
                    {byType.length ? byType.map(([key, count]) => <Badge key={key} variant="outline">{key}: {count}</Badge>) : <span className="text-sm text-muted-foreground">-</span>}
                  </div>
                </div>
                <div className="rounded-2xl border border-border/70 p-4">
                  <div className="mb-2 text-sm font-medium">{t("memoryByStatus", { defaultValue: "By status" })}</div>
                  <div className="flex flex-wrap gap-2">
                    {byStatus.length ? byStatus.map(([key, count]) => <Badge key={key} variant="outline">{key}: {count}</Badge>) : <span className="text-sm text-muted-foreground">-</span>}
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle>{t("memoryChunksTitle", { defaultValue: "Memory chunks" })}</CardTitle>
            <CardDescription>{t("memoryChunksDescription", { defaultValue: "Edit individual memory items or select several to reorganize." })}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading ? (
              <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                {t("memoryPageLoading", { defaultValue: "Loading memories..." })}
              </div>
            ) : items.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                {t("memoryPageEmpty", { defaultValue: "No memories yet." })}
              </div>
            ) : (
              items.map((memory) => {
                const checked = selectedIds.includes(memory.id);
                return (
                  <div key={memory.id} className="rounded-2xl border border-border/70 p-4">
                    <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                      <div className="flex items-start gap-3">
                        <Checkbox
                          checked={checked}
                          onCheckedChange={(value) =>
                            setSelectedIds((prev) =>
                              value
                                ? [...prev, memory.id]
                                : prev.filter((id) => id !== memory.id),
                            )
                          }
                        />
                        <div className="space-y-2">
                          <div className="flex flex-wrap gap-2">
                            <Badge variant="outline">#{memory.id}</Badge>
                            <Badge variant="secondary">{memory.memory_pool}</Badge>
                            <Badge variant="secondary">{memory.memory_type}</Badge>
                            <Badge variant="outline">{memory.status}</Badge>
                            <Badge variant="outline">{memory.source_kind}</Badge>
                            {(memory.tags || []).map((tag) => (
                              <Badge key={`${memory.id}-${tag}`} variant="outline">
                                {tag}
                              </Badge>
                            ))}
                          </div>
                          {memory.summary ? <div className="text-sm font-medium">{memory.summary}</div> : null}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button variant="ghost" size="sm" onClick={() => setEditing(memory)}>
                          <Pencil className="mr-2 size-4" />
                          {t("common.edit", { defaultValue: "Edit" })}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => void handleDeleteMemory(memory)}>
                          <Trash2 className="mr-2 size-4" />
                          {t("deleteMemory", { defaultValue: "Delete" })}
                        </Button>
                      </div>
                    </div>
                    <div className="whitespace-pre-wrap text-sm leading-6">{memory.content}</div>
                    <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
                      <span>{t("importanceWithTime", { importance: memory.importance, time: formatTime(memory.created_at), defaultValue: `importance ${memory.importance} · ${formatTime(memory.created_at)}` })}</span>
                      <span>{t("memoryConfidence", { defaultValue: "confidence" })}: {memory.confidence ?? "-"}</span>
                      <span>{t("memoryAccessCount", { defaultValue: "accesses" })}: {memory.access_count ?? 0}</span>
                      <span>{t("memoryValidUntil", { defaultValue: "valid until" })}: {formatTime(memory.valid_until)}</span>
                    </div>
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={Boolean(editing)} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>{t("memoryEditTitle", { defaultValue: "Edit memory" })}</DialogTitle>
            <DialogDescription>{editing ? `#${editing.id}` : ""}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label>{t("memorySummary", { defaultValue: "Summary" })}</Label>
              <Input value={editSummary} onChange={(event) => setEditSummary(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>{t("memoryContent", { defaultValue: "Content" })}</Label>
              <Textarea value={editContent} onChange={(event) => setEditContent(event.target.value)} rows={10} />
            </div>
            <div className="grid gap-2">
              <Label>{t("memoryTags", { defaultValue: "Tags" })}</Label>
              <Input
                value={editTags}
                onChange={(event) => setEditTags(event.target.value)}
                placeholder={t("memoryTagsPlaceholder", { defaultValue: "Comma-separated tags" })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)}>
              {t("common.cancel", { defaultValue: "Cancel" })}
            </Button>
            <Button onClick={() => void handleSaveEdit()} disabled={isSaving}>
              {isSaving ? t("common.saving", { defaultValue: "Saving..." }) : t("common.save", { defaultValue: "Save" })}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isReorganizeOpen} onOpenChange={setIsReorganizeOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t("memoryReorganizeTitle", { defaultValue: "AI reorganize memories" })}</DialogTitle>
            <DialogDescription>
              {t("memoryReorganizeDescription", {
                count: selectedCount,
                defaultValue: `Reorganize ${selectedCount} selected memories into a cleaner set.`,
              })}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label>{t("memoryReorganizeInstructions", { defaultValue: "Instructions" })}</Label>
            <Textarea
              rows={6}
              value={reorganizeInstructions}
              onChange={(event) => setReorganizeInstructions(event.target.value)}
              placeholder={t("memoryReorganizeInstructionsPlaceholder", {
                defaultValue: "Optional: merge overlap, keep project rules separate, preserve explicit user preferences...",
              })}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsReorganizeOpen(false)}>
              {t("common.cancel", { defaultValue: "Cancel" })}
            </Button>
            <Button onClick={() => void handleReorganize()} disabled={!selectedCount || isReorganizing}>
              {isReorganizing ? t("common.saving", { defaultValue: "Saving..." }) : t("memoryReorganize", { defaultValue: "AI reorganize" })}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {confirmDialog}
    </PageFrame>
  );
}
