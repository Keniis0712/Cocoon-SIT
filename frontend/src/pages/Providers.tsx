import { useEffect, useMemo, useState } from "react";
import { Pencil, Plus, RefreshCcw, Server, Trash2, Wifi } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { showErrorToast } from "@/api/client";
import {
  createModelProvider,
  deleteModelProvider,
  listModelProviders,
  syncModelProvider,
  testModelProvider,
  updateModelProvider,
} from "@/api/providers";
import type { ModelProviderPayload, ModelProviderRead } from "@/api/types/providers";
import AccessCard from "@/components/AccessCard";
import { useConfirmDialog } from "@/components/composes/useConfirmDialog";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useUserStore } from "@/store/useUserStore";

const EMPTY_FORM: ModelProviderPayload = {
  name: "",
  base_url: "",
  api_key: "",
  is_enabled: true,
};

export default function ProvidersPage() {
  const { t } = useTranslation(["providers", "common"]);
  const userInfo = useUserStore((state) => state.userInfo);
  const [items, setItems] = useState<ModelProviderRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<ModelProviderRead | null>(null);
  const [modelsDialogProvider, setModelsDialogProvider] = useState<ModelProviderRead | null>(null);
  const [selectedTestModelId, setSelectedTestModelId] = useState("");
  const [testPrompt, setTestPrompt] = useState("ping");
  const [modelQuery, setModelQuery] = useState("");
  const [form, setForm] = useState<ModelProviderPayload>(EMPTY_FORM);
  const { confirm, confirmDialog } = useConfirmDialog();

  const canManage = Boolean(userInfo?.can_manage_providers);
  const filteredDialogModels = useMemo(() => {
    const normalized = modelQuery.trim().toLowerCase();
    const models = modelsDialogProvider?.available_models || [];
    if (!normalized) {
      return models;
    }
    return models.filter((model) => `${model.model_name} ${model.id}`.toLowerCase().includes(normalized));
  }, [modelQuery, modelsDialogProvider]);

  async function fetchProviders() {
    setIsLoading(true);
    try {
      const response = await listModelProviders(1, 100);
      setItems(response.items);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (canManage) {
      void fetchProviders();
    }
  }, [canManage]);

  function openCreateDialog() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEditDialog(item: ModelProviderRead) {
    setEditing(item);
    setForm({
      name: item.name,
      base_url: item.base_url,
      api_key: "",
      is_enabled: item.is_enabled,
    });
    setDialogOpen(true);
  }

  async function saveProvider() {
    setIsSaving(true);
    try {
      const payload: Partial<ModelProviderPayload> = {
        name: form.name.trim(),
        base_url: form.base_url.trim(),
        is_enabled: form.is_enabled,
      };

      if (form.api_key.trim()) {
        payload.api_key = form.api_key.trim();
      }

      if (editing) {
        await updateModelProvider(editing.id, payload);
        toast.success(t("providers:providerUpdated"));
      } else {
        await createModelProvider({
          name: payload.name || "",
          base_url: payload.base_url || "",
          api_key: payload.api_key || "",
          is_enabled: payload.is_enabled ?? true,
        });
        toast.success(t("providers:providerCreated"));
      }

      setDialogOpen(false);
      setEditing(null);
      setForm(EMPTY_FORM);
      await fetchProviders();
    } catch (error) {
      showErrorToast(error, t("providers:saveFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSyncProvider(item: ModelProviderRead) {
    try {
      await syncModelProvider(item.id);
      toast.success(t("providers:modelsSynced"));
      await fetchProviders();
    } catch (error) {
      showErrorToast(error, t("providers:syncFailed"));
    }
  }

  function openModelsDialog(item: ModelProviderRead) {
    setModelsDialogProvider(item);
    setSelectedTestModelId(String(item.available_models[0]?.id || ""));
    setTestPrompt("ping");
    setModelQuery("");
  }

  async function handleTestProvider(item: ModelProviderRead) {
    if (!item.available_models.length) {
      toast.error(t("providers:noModels"));
      return;
    }
    setIsTesting(true);
    try {
      const result = await testModelProvider(item.id, {
        selected_model_id: Number(selectedTestModelId || item.available_models[0].id),
        prompt: testPrompt.trim() || "ping",
      });
      toast.success(t("providers:testReply", { model: result.model_name, value: result.reply }));
    } catch (error) {
      showErrorToast(error, t("providers:testFailed"));
    } finally {
      setIsTesting(false);
    }
  }

  async function handleDeleteProvider(item: ModelProviderRead) {
    const accepted = await confirm({
      title: t("common:delete"),
      description: t("providers:deleteConfirm", { name: item.name }),
      confirmLabel: t("common:delete"),
      cancelLabel: t("common:cancel"),
      variant: "destructive",
    });
    if (!accepted) {
      return;
    }
    try {
      await deleteModelProvider(item.id);
      toast.success(t("providers:providerDeleted"));
      await fetchProviders();
    } catch (error) {
      showErrorToast(error, t("providers:deleteFailed"));
    }
  }

  if (!canManage) {
    return <AccessCard description={t("providers:noPermission")} />;
  }

  return (
    <PageFrame
      title={t("providers:title")}
      description={t("providers:description")}
      actions={
        <Button onClick={openCreateDialog}>
          <Plus className="mr-2 size-4" />
          {t("providers:newProvider")}
        </Button>
      }
    >
      <div className="grid gap-4 xl:grid-cols-2">
        {isLoading
          ? Array.from({ length: 4 }).map((_, index) => <Card key={index} className="h-64 animate-pulse bg-muted/40" />)
          : items.map((item) => (
              <Card key={item.id} className="border-border/70 bg-card/90">
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <CardTitle className="flex items-center gap-2 text-lg">
                        <Server className="size-4 text-primary" />
                        {item.name}
                      </CardTitle>
                      <CardDescription className="mt-2 break-all">{item.base_url}</CardDescription>
                    </div>
                    <div className="flex flex-col gap-2">
                      <Badge variant="outline">#{item.id}</Badge>
                      <Badge variant={item.is_enabled ? "default" : "secondary"}>
                        {item.is_enabled ? t("providers:enabled") : t("providers:disabled")}
                      </Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4 text-sm">
                  <div>
                    <div className="mb-2 text-muted-foreground">{t("providers:availableModels")}</div>
                    <div className="flex flex-wrap items-center gap-2">
                      {item.available_models.length > 0 ? (
                        <>
                          <Badge variant="outline">{t("providers:modelCount", { count: item.available_models.length })}</Badge>
                          <Button variant="outline" size="sm" onClick={() => openModelsDialog(item)}>
                            {t("providers:browseModels")}
                          </Button>
                        </>
                      ) : (
                        <span className="text-muted-foreground">{t("providers:noModelsRegistered")}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={() => void handleSyncProvider(item)}>
                      <RefreshCcw className="mr-2 size-4" />
                      {t("providers:syncModels")}
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => openModelsDialog(item)}>
                      <Wifi className="mr-2 size-4" />
                      {t("providers:test")}
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => openEditDialog(item)}>
                      <Pencil className="mr-2 size-4" />
                      {t("common:edit")}
                    </Button>
                    <Button variant="destructive" size="sm" onClick={() => void handleDeleteProvider(item)}>
                      <Trash2 className="mr-2 size-4" />
                      {t("common:delete")}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? t("providers:editProvider") : t("providers:createProvider")}</DialogTitle>
            <DialogDescription>{t("providers:dialogDescription")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label htmlFor="provider-name">{t("common:name")}</Label>
              <Input
                id="provider-name"
                value={form.name}
                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="provider-base-url">{t("providers:baseUrl")}</Label>
              <Input
                id="provider-base-url"
                value={form.base_url}
                onChange={(event) => setForm((prev) => ({ ...prev, base_url: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="provider-api-key">
                {editing ? t("providers:apiKeyKeepCurrent") : t("providers:apiKey")}
              </Label>
              <Input
                id="provider-api-key"
                type="password"
                value={form.api_key}
                onChange={(event) => setForm((prev) => ({ ...prev, api_key: event.target.value }))}
              />
            </div>
            <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
              <Checkbox
                checked={form.is_enabled}
                onCheckedChange={(checked) => setForm((prev) => ({ ...prev, is_enabled: Boolean(checked) }))}
              />
              <span>{t("providers:enableProvider")}</span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {t("common:cancel")}
            </Button>
            <Button
              disabled={isSaving || !form.name.trim() || !form.base_url.trim() || (!editing && !form.api_key.trim())}
              onClick={saveProvider}
            >
              {isSaving ? t("providers:saving") : editing ? t("common:saveChanges") : t("providers:createProvider")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={Boolean(modelsDialogProvider)} onOpenChange={(open) => !open && setModelsDialogProvider(null)}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t("providers:modelsDialogTitle")}</DialogTitle>
            <DialogDescription>
              {modelsDialogProvider
                ? `${modelsDialogProvider.name} · ${t("providers:modelsDialogDescription")}`
                : t("providers:modelsDialogDescription")}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>{t("common:search")}</Label>
              <Input value={modelQuery} onChange={(event) => setModelQuery(event.target.value)} placeholder={t("common:search")} />
            </div>
            <div className="grid gap-2">
              <Label>{t("providers:selectedModel")}</Label>
              <div className="max-h-[40vh] overflow-y-auto rounded-2xl border border-border/70 bg-background/60 p-2">
                {filteredDialogModels.length ? (
                  <div className="space-y-2">
                    {filteredDialogModels.map((model) => {
                      const active = selectedTestModelId === String(model.id);
                      return (
                        <button
                          key={model.id}
                          type="button"
                          onClick={() => setSelectedTestModelId(String(model.id))}
                          className={`flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-left transition ${
                            active ? "border-primary bg-primary/8" : "border-border/70 hover:border-primary/40 hover:bg-accent/40"
                          }`}
                        >
                          <div className="min-w-0">
                            <div className="truncate font-medium">{model.model_name}</div>
                            <div className="mt-1 text-xs text-muted-foreground">#{model.id}</div>
                          </div>
                          {active ? <Badge>{t("common:default")}</Badge> : null}
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
                    {t("providers:noModelsMatch")}
                  </div>
                )}
              </div>
            </div>
            <div className="grid gap-2">
              <Label>{t("providers:testPrompt")}</Label>
              <Input value={testPrompt} onChange={(event) => setTestPrompt(event.target.value)} placeholder={t("providers:testPromptPlaceholder")} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModelsDialogProvider(null)}>
              {t("common:cancel")}
            </Button>
            <Button
              disabled={isTesting || !modelsDialogProvider || !selectedTestModelId}
              onClick={() => modelsDialogProvider && void handleTestProvider(modelsDialogProvider)}
            >
              {isTesting ? t("providers:testing") : t("providers:runSingleModelTest")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {confirmDialog}
    </PageFrame>
  );
}
