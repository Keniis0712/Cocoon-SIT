import { useEffect, useState } from "react";
import { FileCode2, Pencil, RotateCcw } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { showErrorToast } from "@/api/client";
import { listPromptTemplates, resetPromptTemplate, savePromptTemplate } from "@/api/prompts";
import type { PromptTemplatePayload, PromptTemplateRead } from "@/api/types/prompts";
import AccessCard from "@/components/AccessCard";
import { useConfirmDialog } from "@/components/composes/useConfirmDialog";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useUserStore } from "@/store/useUserStore";

type TemplateVariableKey =
  | "character_settings"
  | "session_state"
  | "tag_catalog"
  | "visible_messages"
  | "memory_context"
  | "runtime_event"
  | "wakeup_context"
  | "merge_context"
  | "provider_capabilities";

const TEMPLATE_ORDER = [
  "system",
  "meta",
  "generator",
  "memory_summary",
  "pull",
  "merge",
  "audit_summary",
] as const;

const TEMPLATE_VARIABLES: Record<(typeof TEMPLATE_ORDER)[number], TemplateVariableKey[]> = {
  system: ["character_settings", "session_state", "provider_capabilities"],
  meta: [
    "character_settings",
    "session_state",
    "tag_catalog",
    "visible_messages",
    "memory_context",
    "runtime_event",
    "wakeup_context",
    "merge_context",
    "provider_capabilities",
  ],
  generator: [
    "character_settings",
    "session_state",
    "tag_catalog",
    "visible_messages",
    "memory_context",
    "runtime_event",
    "wakeup_context",
    "merge_context",
    "provider_capabilities",
  ],
  memory_summary: ["session_state", "tag_catalog", "visible_messages", "memory_context"],
  pull: ["runtime_event", "memory_context"],
  merge: ["runtime_event", "merge_context"],
  audit_summary: ["runtime_event", "visible_messages"],
};

const EMPTY_FORM: PromptTemplatePayload = {
  name: "",
  description: "",
  content: "",
};

function checksumLabel(value: string) {
  return value.slice(0, 10);
}

export default function PromptTemplatesPage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const [items, setItems] = useState<PromptTemplateRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [resettingType, setResettingType] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<PromptTemplateRead | null>(null);
  const [form, setForm] = useState<PromptTemplatePayload>(EMPTY_FORM);
  const { confirm, confirmDialog } = useConfirmDialog();

  const canManage = Boolean(userInfo?.can_manage_prompts);

  async function fetchTemplates() {
    setIsLoading(true);
    try {
      const response = await listPromptTemplates();
      const ordered = [...response].sort((left, right) => {
        const leftIndex = TEMPLATE_ORDER.indexOf(left.template_type as (typeof TEMPLATE_ORDER)[number]);
        const rightIndex = TEMPLATE_ORDER.indexOf(right.template_type as (typeof TEMPLATE_ORDER)[number]);
        return (leftIndex === -1 ? Number.MAX_SAFE_INTEGER : leftIndex) - (rightIndex === -1 ? Number.MAX_SAFE_INTEGER : rightIndex);
      });
      setItems(ordered);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (canManage) {
      void fetchTemplates();
    }
  }, [canManage]);

  function openEditDialog(item: PromptTemplateRead) {
    setEditing(item);
    setForm({
      name: item.name,
      description: item.description,
      content: item.active_revision?.content || "",
    });
    setDialogOpen(true);
  }

  function insertPlaceholder(name: string) {
    setForm((prev) => ({
      ...prev,
      content: `${prev.content}${prev.content.endsWith("\n") || prev.content.length === 0 ? "" : "\n"}{{ ${name} }}`,
    }));
  }

  async function handleSave() {
    if (!editing) {
      return;
    }
    setIsSaving(true);
    try {
      await savePromptTemplate(editing.template_type, {
        name: form.name.trim(),
        description: form.description.trim(),
        content: form.content,
      });
      toast.success(t("prompts.saved"));
      setDialogOpen(false);
      await fetchTemplates();
    } catch (error) {
      showErrorToast(error, t("prompts.saveFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleReset(item: PromptTemplateRead) {
    const templateName = t(`prompts.types.${item.template_type}.name`, { defaultValue: item.name });
    const accepted = await confirm({
      title: t("prompts.reset"),
      description: t("prompts.resetConfirm", { name: templateName }),
      confirmLabel: t("prompts.reset"),
      cancelLabel: t("common.cancel"),
      variant: "destructive",
    });
    if (!accepted) {
      return;
    }

    setResettingType(item.template_type);
    try {
      await resetPromptTemplate(item.template_type);
      toast.success(t("prompts.resetDone"));
      if (editing?.template_type === item.template_type) {
        setDialogOpen(false);
      }
      await fetchTemplates();
    } catch (error) {
      showErrorToast(error, t("prompts.resetFailed"));
    } finally {
      setResettingType(null);
    }
  }

  if (!canManage) {
    return <AccessCard description={t("prompts.noPermission")} />;
  }

  return (
    <PageFrame
      title={t("prompts.title")}
      description={t("prompts.description")}
      actions={
        <Button asChild variant="outline">
          <Link to="/settings">{t("prompts.backToSettings")}</Link>
        </Button>
      }
    >
      <div className="mb-6">
        <Card className="border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle className="text-base">{t("prompts.statusTitle")}</CardTitle>
            <CardDescription>{t("prompts.statusDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            <div className="rounded-2xl border border-border/70 p-4">
              <div className="mb-2">{t("prompts.statusTemplates")}</div>
              <div className="text-2xl font-semibold text-foreground">{items.length}</div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {isLoading
          ? Array.from({ length: 6 }).map((_, index) => <Card key={index} className="h-72 animate-pulse bg-muted/40" />)
          : items.map((item) => {
              const allowedVariables = TEMPLATE_VARIABLES[item.template_type as (typeof TEMPLATE_ORDER)[number]] || [];
              return (
                <Card key={item.id} className="border-border/70 bg-card/90">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <CardTitle className="flex items-center gap-2 text-lg">
                          <FileCode2 className="size-4 text-primary" />
                          {t(`prompts.types.${item.template_type}.name`, { defaultValue: item.name })}
                        </CardTitle>
                        <CardDescription className="mt-2">
                          {item.description || t(`prompts.types.${item.template_type}.description`, { defaultValue: item.template_type })}
                        </CardDescription>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <Badge variant="outline">{item.template_type}</Badge>
                        {item.active_revision ? <Badge>v{item.active_revision.version}</Badge> : null}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4 text-sm">
                    <div>
                      <div className="mb-2 text-muted-foreground">{t("prompts.allowedVariables")}</div>
                      <div className="flex flex-wrap gap-2">
                        {allowedVariables.map((name) => (
                          <Badge key={name} variant="outline">
                            {name}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-border/70 p-4">
                      <div className="mb-2 text-muted-foreground">{t("prompts.activeRevision")}</div>
                      {item.active_revision ? (
                        <div className="space-y-2 text-xs text-muted-foreground">
                          <div>{t("prompts.version")}: v{item.active_revision.version}</div>
                          <div>{t("prompts.checksum")}: {checksumLabel(item.active_revision.checksum)}</div>
                          <div>{t("common.createdAt")}: {new Date(item.active_revision.created_at).toLocaleString()}</div>
                        </div>
                      ) : (
                        <div className="text-xs text-muted-foreground">{t("prompts.noActiveRevision")}</div>
                      )}
                    </div>
                    <div className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded-2xl border border-dashed border-border/70 p-4 text-xs leading-6 text-muted-foreground scrollbar-thin scrollbar-track-transparent scrollbar-thumb-border/80">
                      {item.active_revision?.content || t("prompts.noContent")}
                    </div>
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={resettingType === item.template_type}
                        onClick={() => void handleReset(item)}
                      >
                        <RotateCcw className="mr-2 size-4" />
                        {t("prompts.reset")}
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => openEditDialog(item)}>
                        <Pencil className="mr-2 size-4" />
                        {t("common.edit")}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-5xl">
          <DialogHeader>
            <DialogTitle>{editing ? t("prompts.editTitle", { name: t(`prompts.types.${editing.template_type}.name`, { defaultValue: editing.name }) }) : t("prompts.title")}</DialogTitle>
            <DialogDescription>{t("prompts.dialogDescription")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-6 py-2 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="space-y-4">
              <div className="grid gap-2">
                <Label htmlFor="prompt-template-name">{t("common.name")}</Label>
                <Input
                  id="prompt-template-name"
                  value={form.name}
                  onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="prompt-template-description">{t("common.description")}</Label>
                <Textarea
                  id="prompt-template-description"
                  rows={3}
                  className="max-h-36"
                  value={form.description}
                  onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="prompt-template-content">{t("prompts.content")}</Label>
                <Textarea
                  id="prompt-template-content"
                  rows={18}
                  className="max-h-[60vh] font-mono text-xs"
                  value={form.content}
                  onChange={(event) => setForm((prev) => ({ ...prev, content: event.target.value }))}
                />
              </div>
            </div>

            <div>
              <Card className="border-border/70 bg-background/30">
                <CardHeader>
                  <CardTitle className="text-base">{t("prompts.helperTitle")}</CardTitle>
                  <CardDescription>{t("prompts.helperDescription")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {(editing ? TEMPLATE_VARIABLES[editing.template_type as (typeof TEMPLATE_ORDER)[number]] || [] : []).map((name) => (
                    <div key={name} className="rounded-2xl border border-border/70 p-3 text-sm">
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <Badge variant="outline">{name}</Badge>
                        <Button variant="ghost" size="sm" onClick={() => insertPlaceholder(name)}>
                          {t("prompts.insert")}
                        </Button>
                      </div>
                      <div className="text-muted-foreground">
                        {t(`prompts.variables.${name}`)}
                      </div>
                    </div>
                  ))}
                  {editing && ["meta", "generator", "memory_summary"].includes(editing.template_type) ? (
                    <div className="rounded-2xl border border-border/70 bg-muted/20 p-3 text-sm text-muted-foreground">
                      <div className="font-medium text-foreground">Tag Catalog Note</div>
                      <div className="mt-2">
                        `tag_catalog` is a numbered allowlist. Models must output the index only, never a free-text tag name.
                      </div>
                      <div className="mt-2 font-mono text-xs">
                        Example: {`{"tag_ops":[{"action":"add","tag_index":1}]}`}
                      </div>
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            </div>
          </div>
          <DialogFooter>
            {editing ? (
              <Button
                variant="outline"
                disabled={resettingType === editing.template_type}
                onClick={() => void handleReset(editing)}
              >
                <RotateCcw className="mr-2 size-4" />
                {t("prompts.reset")}
              </Button>
            ) : null}
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button disabled={isSaving || !form.name.trim() || !form.content.trim()} onClick={() => void handleSave()}>
              {isSaving ? t("common.saving") : t("common.saveChanges")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {confirmDialog}
    </PageFrame>
  );
}
