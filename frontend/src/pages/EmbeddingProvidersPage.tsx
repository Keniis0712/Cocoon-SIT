import { useEffect, useState } from "react";
import { Pencil, Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { showErrorToast } from "@/api/client";
import { createEmbeddingProvider, listEmbeddingProviders, updateEmbeddingProvider } from "@/api/embeddingProviders";
import type { EmbeddingProviderPayload, EmbeddingProviderRead } from "@/api/types/providers";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const EMPTY_FORM: EmbeddingProviderPayload = {
  name: "",
  kind: "local_cpu",
  base_url: "",
  api_key: "",
  model_name: "",
  local_model_name: "",
  device: "cpu",
  is_enabled: true,
  is_default: false,
};

export default function EmbeddingProvidersPage() {
  const { t } = useTranslation(["providers", "common"]);
  const [items, setItems] = useState<EmbeddingProviderRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<EmbeddingProviderRead | null>(null);
  const [form, setForm] = useState<EmbeddingProviderPayload>(EMPTY_FORM);

  useEffect(() => {
    void fetchItems();
  }, []);

  async function fetchItems() {
    setIsLoading(true);
    try {
      const response = await listEmbeddingProviders(1, 100);
      setItems(response.items);
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("providers:embeddingLoadFailed"));
    } finally {
      setIsLoading(false);
    }
  }

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEdit(item: EmbeddingProviderRead) {
    setEditing(item);
    setForm({
      name: item.name,
      kind: item.kind,
      base_url: item.base_url || "",
      api_key: "",
      model_name: item.model_name || "",
      local_model_name: item.local_model_name || "",
      device: item.device,
      is_enabled: item.is_enabled,
      is_default: item.is_default,
    });
    setDialogOpen(true);
  }

  async function handleSave() {
    try {
      if (editing) {
        await updateEmbeddingProvider(editing.id, form);
        toast.success(t("providers:embeddingUpdated"));
      } else {
        await createEmbeddingProvider(form);
        toast.success(t("providers:embeddingCreated"));
      }
      setDialogOpen(false);
      await fetchItems();
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("providers:embeddingSaveFailed"));
    }
  }

  return (
    <PageFrame
      title={t("providers:embeddingTitle")}
      description={t("providers:embeddingDescription")}
      actions={
        <Button onClick={openCreate}>
          <Plus className="mr-2 size-4" />
          {t("providers:newEmbeddingProvider")}
        </Button>
      }
    >
      <div className="grid gap-4 xl:grid-cols-2">
        {isLoading ? (
          <Card className="h-48 animate-pulse bg-muted/40" />
        ) : (
          items.map((item) => (
            <Card key={item.id} className="border-border/70 bg-card/90">
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle>{item.name}</CardTitle>
                    <CardDescription className="mt-2">{item.kind}</CardDescription>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => openEdit(item)}>
                    <Pencil className="mr-2 size-4" />
                    {t("common:edit")}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex flex-wrap gap-2">
                  {item.is_default ? <Badge>{t("providers:defaultBadge")}</Badge> : null}
                  <Badge variant={item.is_enabled ? "default" : "secondary"}>
                    {item.is_enabled ? t("providers:enabled") : t("providers:disabled")}
                  </Badge>
                </div>
                <div className="text-muted-foreground">{t("providers:baseUrlValue", { value: item.base_url || "-" })}</div>
                <div className="text-muted-foreground">{t("providers:remoteModelValue", { value: item.model_name || "-" })}</div>
                <div className="text-muted-foreground">{t("providers:localModelValue", { value: item.local_model_name || "-" })}</div>
                <div className="text-muted-foreground">{t("providers:deviceValue", { value: item.device })}</div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? t("providers:editEmbeddingProvider") : t("providers:newEmbeddingProvider")}</DialogTitle>
            <DialogDescription>
              {t("providers:embeddingDialogDescription")}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>{t("common:name")}</Label>
              <Input value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>{t("providers:kind")}</Label>
              <Select value={form.kind} onValueChange={(value) => setForm((prev) => ({ ...prev, kind: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="local_cpu">local_cpu</SelectItem>
                  <SelectItem value="openai_compatible">openai_compatible</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>{t("providers:baseUrl")}</Label>
              <Input value={form.base_url || ""} onChange={(event) => setForm((prev) => ({ ...prev, base_url: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>{t("providers:apiKey")}</Label>
              <Input type="password" value={form.api_key || ""} onChange={(event) => setForm((prev) => ({ ...prev, api_key: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>{t("providers:remoteModel")}</Label>
              <Input value={form.model_name || ""} onChange={(event) => setForm((prev) => ({ ...prev, model_name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>{t("providers:localModel")}</Label>
              <Input value={form.local_model_name || ""} onChange={(event) => setForm((prev) => ({ ...prev, local_model_name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>{t("providers:device")}</Label>
              <Input value={form.device || "cpu"} onChange={(event) => setForm((prev) => ({ ...prev, device: event.target.value }))} />
            </div>
            <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
              <Checkbox checked={form.is_enabled} onCheckedChange={(checked) => setForm((prev) => ({ ...prev, is_enabled: Boolean(checked) }))} />
              <span>{t("providers:enableEmbeddingProvider")}</span>
            </label>
            <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
              <Checkbox checked={form.is_default} onCheckedChange={(checked) => setForm((prev) => ({ ...prev, is_default: Boolean(checked) }))} />
              <span>{t("providers:setAsDefault")}</span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {t("common:cancel")}
            </Button>
            <Button disabled={!form.name.trim()} onClick={handleSave}>
              {t("common:save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageFrame>
  );
}
