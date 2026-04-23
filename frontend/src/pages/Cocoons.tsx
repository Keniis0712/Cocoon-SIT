import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { BrainCircuit, ChevronRight, Edit3, Loader2, Plus, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { getErrorMessage, showErrorToast } from "@/api/client";
import { getCharacters } from "@/api/characters";
import { createCocoon, deleteCocoon, getCocoon, getCocoonTree, updateCocoon } from "@/api/cocoons";
import { listModelProviders } from "@/api/providers";
import type { CharacterRead } from "@/api/types/catalog";
import type { CocoonPayload, CocoonRead, CocoonTreeNode } from "@/api/types/cocoons";
import type { ModelProviderRead } from "@/api/types/providers";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type TreeNodeState = CocoonTreeNode & {
  childIds: number[];
  page: number;
  hasMore: boolean;
  isLoading: boolean;
};

type CocoonDialogMode = "create-root" | "create-child" | "edit";

type CocoonFormState = {
  name: string;
  character_id: string;
  selected_model_id: string;
  max_context_messages: string;
  auto_compaction_enabled: boolean;
};

const ROOT_PAGE_SIZE = 20;
const CHILD_PAGE_SIZE = 20;
const UNSET = "__unset";
const INHERIT = "__inherit";
const EMPTY_ROOT_FORM: CocoonFormState = {
  name: "",
  character_id: UNSET,
  selected_model_id: UNSET,
  max_context_messages: "",
  auto_compaction_enabled: true,
};

function mergeIds(existing: number[], incoming: number[]) {
  return Array.from(new Set([...existing, ...incoming]));
}

function normalizeTree(items: CocoonTreeNode[], patch: Record<number, TreeNodeState>): number[] {
  return items.map((item) => {
    const childIds = normalizeTree(item.children || [], patch);
    patch[item.id] = {
      ...item,
      childIds,
      page: 1,
      hasMore: false,
      isLoading: false,
    };
    return item.id;
  });
}

function formatTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "-";
}

function parseNumber(value: string) {
  const normalized = value.trim();
  return normalized ? Number(normalized) : undefined;
}

function friendlyCocoonErrorMessage(rawMessage: string) {
  if (rawMessage.includes("A root cocoon already exists for this user and character")) {
    return "You already have a private root cocoon for this character. Open the existing one, or create a child cocoon to continue from it.";
  }
  return rawMessage;
}

function buildModelOptions(providers: ModelProviderRead[]) {
  return providers.flatMap((provider) =>
    provider.available_models.map((model) => ({
      id: model.id,
      label: `${provider.name} / ${model.model_name}`,
    })),
  );
}

function TruthBadge({
  enabled,
  onText,
  offText,
}: {
  enabled: boolean | null | undefined;
  onText: string;
  offText: string;
}) {
  if (enabled == null) {
    return <span className="text-muted-foreground">-</span>;
  }
  return <Badge variant={enabled ? "default" : "secondary"}>{enabled ? onText : offText}</Badge>;
}

export default function CocoonsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [treeNodes, setTreeNodes] = useState<Record<number, TreeNodeState>>({});
  const [rootIds, setRootIds] = useState<number[]>([]);
  const [rootMeta, setRootMeta] = useState({ page: 1, hasMore: false, isLoading: true });
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [characters, setCharacters] = useState<CharacterRead[]>([]);
  const [providers, setProviders] = useState<ModelProviderRead[]>([]);
  const [selectedCocoonId, setSelectedCocoonId] = useState<number | null>(null);
  const [selectedCocoon, setSelectedCocoon] = useState<CocoonRead | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<CocoonDialogMode>("create-root");
  const [form, setForm] = useState<CocoonFormState>(EMPTY_ROOT_FORM);
  const [isSaving, setIsSaving] = useState(false);

  const modelOptions = useMemo(() => buildModelOptions(providers), [providers]);

  useEffect(() => {
    void fetchReferenceData();
    void loadTree(null, 1, true);
  }, []);

  async function fetchReferenceData() {
    try {
      const [characterResponse, providerResponse] = await Promise.all([
        getCharacters(1, 100, "all"),
        listModelProviders(1, 100),
      ]);
      setCharacters(characterResponse.items);
      setProviders(providerResponse.items);
    } catch (error) {
      showErrorToast(error, t("cocoons.loadReferenceFailed"));
    }
  }

  async function loadTree(parentId: number | null, page: number, selectFirst = false) {
    if (parentId === null) {
      setRootMeta((prev) => ({ ...prev, isLoading: true }));
    } else {
      setTreeNodes((prev) =>
        prev[parentId]
          ? { ...prev, [parentId]: { ...prev[parentId], isLoading: true } }
          : prev,
      );
    }

    try {
      const response = await getCocoonTree(page, parentId === null ? ROOT_PAGE_SIZE : CHILD_PAGE_SIZE, 2, parentId ?? "");
      const patch: Record<number, TreeNodeState> = {};
      const fetchedIds = normalizeTree(response.items, patch);

      setTreeNodes((prev) => {
        const next = { ...prev };
        for (const [rawId, node] of Object.entries(patch)) {
          const nodeId = Number(rawId);
          next[nodeId] = {
            ...(next[nodeId] || node),
            ...node,
            childIds: node.childIds,
            isLoading: false,
          };
        }

        if (parentId !== null && next[parentId]) {
          next[parentId] = {
            ...next[parentId],
            childIds: page === 1 ? fetchedIds : mergeIds(next[parentId].childIds, fetchedIds),
            page: response.page,
            hasMore: response.page < response.total_pages,
            isLoading: false,
          };
        }

        return next;
      });

      if (parentId === null) {
        setRootIds((prev) => (page === 1 ? fetchedIds : mergeIds(prev, fetchedIds)));
        setRootMeta({ page: response.page, hasMore: response.page < response.total_pages, isLoading: false });
      }

      if (selectFirst && fetchedIds[0] && !selectedCocoonId) {
        await loadSelectedCocoon(fetchedIds[0]);
      }
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("cocoons.loadTreeFailed"));
      if (parentId === null) {
        setRootMeta((prev) => ({ ...prev, isLoading: false }));
      }
    }
  }

  async function loadSelectedCocoon(cocoonId: number) {
    setSelectedCocoonId(cocoonId);
    setIsDetailLoading(true);
    try {
      const cocoon = await getCocoon(cocoonId);
      setSelectedCocoon(cocoon);
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("cocoons.loadDetailFailed"));
    } finally {
      setIsDetailLoading(false);
    }
  }

  function toggleNode(nodeId: number) {
    const willExpand = !expandedIds.has(nodeId);
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (willExpand) next.add(nodeId);
      else next.delete(nodeId);
      return next;
    });

    const node = treeNodes[nodeId];
    if (willExpand && node && node.childIds.length === 0 && node.has_children) {
      void loadTree(nodeId, 1);
    }
  }

  function openCreateRoot() {
    setDialogMode("create-root");
    setForm(EMPTY_ROOT_FORM);
    setDialogOpen(true);
  }

  function openCreateChild() {
    if (!selectedCocoon) return;
    setDialogMode("create-child");
    setForm({
      name: `${selectedCocoon.name} / child`,
      character_id: INHERIT,
      selected_model_id: INHERIT,
      max_context_messages: "",
      auto_compaction_enabled: selectedCocoon.auto_compaction_enabled ?? true,
    });
    setDialogOpen(true);
  }

  function openEditCocoon() {
    if (!selectedCocoon) return;
    setDialogMode("edit");
    setForm({
      name: selectedCocoon.name,
      character_id: String(selectedCocoon.character_id),
      selected_model_id: String(selectedCocoon.selected_model_id),
      max_context_messages:
        selectedCocoon.max_context_messages != null ? String(selectedCocoon.max_context_messages) : "",
      auto_compaction_enabled: selectedCocoon.auto_compaction_enabled ?? true,
    });
    setDialogOpen(true);
  }

  async function saveCocoon() {
    const name = form.name.trim();
    if (!name) return;

    setIsSaving(true);
    try {
      const payload: Partial<CocoonPayload> = {
        name,
        max_context_messages: parseNumber(form.max_context_messages),
        auto_compaction_enabled: form.auto_compaction_enabled,
      };

      if (dialogMode === "create-root") {
        payload.character_id = form.character_id !== UNSET ? Number(form.character_id) : undefined;
        payload.selected_model_id = form.selected_model_id !== UNSET ? Number(form.selected_model_id) : undefined;
      }

      if (dialogMode === "create-child") {
        payload.parent_id = selectedCocoonId;
        if (form.character_id !== INHERIT && form.character_id !== UNSET) payload.character_id = Number(form.character_id);
        if (form.selected_model_id !== INHERIT && form.selected_model_id !== UNSET) payload.selected_model_id = Number(form.selected_model_id);
      }

      if (dialogMode === "edit" && selectedCocoonId) {
        payload.character_id = form.character_id !== UNSET ? Number(form.character_id) : undefined;
        payload.selected_model_id = form.selected_model_id !== UNSET ? Number(form.selected_model_id) : undefined;
      }

      let result: CocoonRead;
      if (dialogMode === "edit" && selectedCocoonId) {
        result = await updateCocoon(selectedCocoonId, payload);
        toast.success(t("cocoons.updated"));
      } else {
        result = await createCocoon(payload as CocoonPayload);
        toast.success(t(dialogMode === "create-child" ? "cocoons.childCreated" : "cocoons.rootCreated"));
      }

      setDialogOpen(false);
      await loadTree(null, 1);
      if (dialogMode === "create-child" && selectedCocoonId) {
        setExpandedIds((prev) => new Set(prev).add(selectedCocoonId));
        await loadTree(selectedCocoonId, 1);
      }
      await loadSelectedCocoon(result.id);
    } catch (error) {
      const message = friendlyCocoonErrorMessage(getErrorMessage(error));
      toast.error(message && !message.startsWith("Request failed with status") ? message : t("cocoons.saveFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDeleteSelectedCocoon() {
    if (!selectedCocoon) return;
    if (!window.confirm(t("cocoons.confirmDeletePrompt", { name: selectedCocoon.name }))) {
      return;
    }
    try {
      await deleteCocoon(selectedCocoon.id);
      toast.success(t("cocoons.deleted"));
      setSelectedCocoon(null);
      setSelectedCocoonId(null);
      await loadTree(null, 1, true);
    } catch (error) {
      showErrorToast(error, t("cocoons.deleteFailed"));
    }
  }

  function renderTreeNode(nodeId: number, level: number): ReactNode {
    const node = treeNodes[nodeId];
    if (!node) return null;

    const isExpanded = expandedIds.has(nodeId);
    const isSelected = selectedCocoonId === nodeId;

    return (
      <div key={nodeId} className="space-y-2">
        <div
          className={`group flex items-center gap-2 rounded-2xl border px-3 py-3 text-sm transition ${
            isSelected
              ? "border-primary bg-primary/5 shadow-sm"
              : "border-border/70 bg-background/70 hover:border-primary/40 hover:bg-accent/30"
          }`}
          style={{ marginLeft: `${level * 16}px` }}
        >
          <button
            type="button"
            className="flex size-8 items-center justify-center rounded-lg hover:bg-accent disabled:opacity-40"
            disabled={!node.has_children}
            onClick={() => toggleNode(nodeId)}
          >
            <ChevronRight className={`size-4 transition ${isExpanded ? "rotate-90" : ""}`} />
          </button>
          <button type="button" className="min-w-0 flex-1 text-left" onClick={() => loadSelectedCocoon(nodeId)}>
            <div className="truncate font-medium">{node.name}</div>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span>#{node.id}</span>
              {node.has_children ? <Badge variant="secondary">{t("cocoons.hasChildren")}</Badge> : null}
              {node.parent_id ? <span>{t("cocoons.parent", { id: node.parent_id })}</span> : <span>{t("cocoons.root")}</span>}
            </div>
          </button>
          <Button variant="ghost" size="sm" onClick={() => navigate(`/cocoons/${nodeId}`)}>
            {t("cocoons.enter")}
          </Button>
          {node.isLoading ? <Loader2 className="size-4 animate-spin text-muted-foreground" /> : null}
        </div>
        {isExpanded ? (
          <div className="space-y-2">
            {node.childIds.map((childId) => renderTreeNode(childId, level + 1))}
            {node.hasMore ? (
              <Button
                variant="ghost"
                size="sm"
                className="ml-8"
                onClick={() => loadTree(nodeId, (treeNodes[nodeId]?.page || 1) + 1)}
              >
                {t("cocoons.loadMoreChildren")}
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <PageFrame
      title={t("cocoons.title")}
      description={t("cocoons.description")}
      actions={
        <>
          <Button variant="outline" onClick={openCreateRoot}>
            <Plus className="mr-2 size-4" />
            {t("cocoons.newRoot")}
          </Button>
          {selectedCocoon ? (
            <Button onClick={openCreateChild}>
              <Plus className="mr-2 size-4" />
              {t("cocoons.newChild")}
            </Button>
          ) : null}
        </>
      }
    >
      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card className="min-h-[72vh] border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle>{t("cocoons.treeTitle")}</CardTitle>
            <CardDescription>{t("cocoons.treeDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {rootMeta.isLoading && rootIds.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
                {t("cocoons.treeLoading")}
              </div>
            ) : rootIds.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
                {t("cocoons.treeEmpty")}
              </div>
            ) : (
              rootIds.map((nodeId) => renderTreeNode(nodeId, 0))
            )}
            {rootMeta.hasMore ? (
              <Button variant="ghost" size="sm" onClick={() => loadTree(null, rootMeta.page + 1)}>
                {t("cocoons.loadMoreRoots")}
              </Button>
            ) : null}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card className="border-border/70 bg-card/90">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BrainCircuit className="size-4 text-primary" />
                {t("cocoons.selectedTitle")}
              </CardTitle>
              <CardDescription>{t("cocoons.selectedDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              {isDetailLoading ? (
                <div className="rounded-lg border border-dashed border-border p-6 text-muted-foreground">
                  {t("cocoons.detailLoading")}
                </div>
              ) : selectedCocoon ? (
                <>
                  <div className="rounded-2xl border border-border/70 bg-background/60 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="text-lg font-semibold">{selectedCocoon.name}</div>
                        <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                          <span>#{selectedCocoon.id}</span>
                          <span>
                            {selectedCocoon.parent_id
                              ? t("cocoons.parent", { id: selectedCocoon.parent_id })
                              : t("cocoons.root")}
                          </span>
                          <span>
                            {t("common.createdAt")}: {formatTime(selectedCocoon.created_at)}
                          </span>
                        </div>
                      </div>
                      <Badge variant="outline">{t("cocoons.structureNode")}</Badge>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button onClick={() => navigate(`/cocoons/${selectedCocoon.id}`)}>
                        <Sparkles className="mr-2 size-4" />
                        {t("cocoons.enterWorkspace")}
                      </Button>
                      <Button variant="outline" onClick={() => navigate(`/merges?sourceCocoonId=${selectedCocoon.id}`)}>
                        {t("cocoons.startMerge")}
                      </Button>
                      <Button variant="outline" onClick={openEditCocoon}>
                        <Edit3 className="mr-2 size-4" />
                        {t("common.edit")}
                      </Button>
                      <Button variant="outline" onClick={() => navigate(`/audits?cocoonId=${selectedCocoon.id}`)}>
                        {t("common.viewAudits")}
                      </Button>
                      <Button variant="destructive" onClick={() => void handleDeleteSelectedCocoon()}>
                        {t("common.delete")}
                      </Button>
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-2xl border border-border/70 p-4">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("common.role")}</div>
                      <div className="mt-2 font-medium">{selectedCocoon.character?.name || "-"}</div>
                    </div>
                    <div className="rounded-2xl border border-border/70 p-4">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("common.model")}</div>
                      <div className="mt-2 font-medium">{selectedCocoon.selected_model?.model_name || "-"}</div>
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-2xl border border-border/70 p-4">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">
                        {t("cocoons.maxContextMessages")}
                      </div>
                      <div className="mt-2 font-medium">
                        {selectedCocoon.max_context_messages ?? t("common.default")}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-border/70 p-4">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">
                        {t("cocoons.autoCompaction")}
                      </div>
                      <div className="mt-2 font-medium">
                        <TruthBadge
                          enabled={selectedCocoon.auto_compaction_enabled}
                          onText={t("cocoons.enabled")}
                          offText={t("cocoons.disabled")}
                        />
                      </div>
                    </div>
                    <div className="rounded-2xl border border-border/70 p-4">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">
                        {t("cocoons.defaultTemperature")}
                      </div>
                      <div className="mt-2 font-medium">
                        {selectedCocoon.default_temperature != null
                          ? selectedCocoon.default_temperature.toFixed(1)
                          : t("common.default")}
                      </div>
                    </div>
                  </div>

                </>
              ) : (
                <div className="rounded-lg border border-dashed border-border p-6 text-muted-foreground">
                  {t("cocoons.emptySelection")}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {dialogMode === "edit"
                ? t("cocoons.dialogEdit")
                : dialogMode === "create-child"
                  ? t("cocoons.dialogCreateChild")
                  : t("cocoons.dialogCreateRoot")}
            </DialogTitle>
            <DialogDescription>
              {dialogMode === "create-child"
                ? t("cocoons.dialogCreateChildDescription")
                : t("cocoons.dialogDefaultDescription")}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>{t("common.name")}</Label>
              <Input value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t("common.role")}</Label>
                <Select value={form.character_id} onValueChange={(value) => setForm((prev) => ({ ...prev, character_id: value }))}>
                  <SelectTrigger>
                    <SelectValue placeholder={t("cocoons.selectRole")} />
                  </SelectTrigger>
                  <SelectContent>
                    {dialogMode === "create-child" ? (
                      <SelectItem value={INHERIT}>{t("cocoons.inheritParent")}</SelectItem>
                    ) : null}
                    {dialogMode !== "create-child" ? (
                      <SelectItem value={UNSET}>{t("cocoons.selectRole")}</SelectItem>
                    ) : null}
                    {characters.map((character) => (
                      <SelectItem key={character.id} value={String(character.id)}>
                        {character.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>{t("common.model")}</Label>
                <Select
                  value={form.selected_model_id}
                  onValueChange={(value) => setForm((prev) => ({ ...prev, selected_model_id: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t("cocoons.selectModel")} />
                  </SelectTrigger>
                  <SelectContent>
                    {dialogMode === "create-child" ? (
                      <SelectItem value={INHERIT}>{t("cocoons.inheritParent")}</SelectItem>
                    ) : null}
                    {dialogMode !== "create-child" ? (
                      <SelectItem value={UNSET}>{t("cocoons.selectModel")}</SelectItem>
                    ) : null}
                    {modelOptions.map((model) => (
                      <SelectItem key={model.id} value={String(model.id)}>
                        {model.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t("cocoons.maxContextMessages")}</Label>
                <Input
                  value={form.max_context_messages}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, max_context_messages: event.target.value }))
                  }
                  placeholder={t("cocoons.emptyUseDefault")}
                />
              </div>
              <label className="mt-8 flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
                <Checkbox
                  checked={form.auto_compaction_enabled}
                  onCheckedChange={(checked) =>
                    setForm((prev) => ({ ...prev, auto_compaction_enabled: Boolean(checked) }))
                  }
                />
                <span>{t("cocoons.autoCompaction")}</span>
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              disabled={
                isSaving ||
                !form.name.trim() ||
                (dialogMode === "create-root" && (form.character_id === UNSET || form.selected_model_id === UNSET))
              }
              onClick={saveCocoon}
            >
              {isSaving
                ? t("common.saving")
                : dialogMode === "edit"
                  ? t("common.saveChanges")
                  : dialogMode === "create-child"
                    ? t("cocoons.dialogCreateChild")
                    : t("cocoons.dialogCreateRoot")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageFrame>
  );
}
