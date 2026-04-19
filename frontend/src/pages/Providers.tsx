import { useEffect, useState } from "react";
import { isAxiosError } from "axios";
import { Pencil, Plus, RefreshCcw, Server, Trash2, Wifi } from "lucide-react";
import { toast } from "sonner";

import {
  createModelProvider,
  deleteModelProvider,
  listModelProviders,
  syncModelProvider,
  testModelProvider,
  updateModelProvider,
} from "@/api/providers";
import type { ModelProviderPayload, ModelProviderRead } from "@/api/types";
import AccessCard from "@/components/AccessCard";
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
  const userInfo = useUserStore((state) => state.userInfo);
  const [items, setItems] = useState<ModelProviderRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<ModelProviderRead | null>(null);
  const [form, setForm] = useState<ModelProviderPayload>(EMPTY_FORM);

  const canManage = Boolean(userInfo?.can_manage_providers);

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
        toast.success("Provider updated");
      } else {
        await createModelProvider({
          name: payload.name || "",
          base_url: payload.base_url || "",
          api_key: payload.api_key || "",
          is_enabled: payload.is_enabled ?? true,
        });
        toast.success("Provider created");
      }

      setDialogOpen(false);
      setEditing(null);
      setForm(EMPTY_FORM);
      await fetchProviders();
    } catch (error) {
      if (isAxiosError(error)) {
        toast.error(String(error.response?.data?.detail || error.message));
      } else {
        toast.error(error instanceof Error ? error.message : "Failed to save provider");
      }
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSyncProvider(item: ModelProviderRead) {
    try {
      await syncModelProvider(item.id);
      toast.success("Provider models synced");
      await fetchProviders();
    } catch (error) {
      if (isAxiosError(error)) {
        toast.error(String(error.response?.data?.detail || error.message));
      } else {
        toast.error(error instanceof Error ? error.message : "Failed to sync provider models");
      }
    }
  }

  async function handleTestProvider(item: ModelProviderRead) {
    if (!item.available_models.length) {
      toast.error("No model is registered for this provider yet");
      return;
    }
    try {
      const result = await testModelProvider(item.id, {
        selected_model_id: item.available_models[0].id,
        prompt: "ping",
      });
      toast.success(`Reply: ${result.reply}`);
    } catch (error) {
      if (isAxiosError(error)) {
        toast.error(String(error.response?.data?.detail || error.message));
      } else {
        toast.error(error instanceof Error ? error.message : "Failed to test provider");
      }
    }
  }

  async function handleDeleteProvider(item: ModelProviderRead) {
    if (!window.confirm(`Delete provider "${item.name}"?`)) {
      return;
    }
    try {
      await deleteModelProvider(item.id);
      toast.success("Provider deleted");
      await fetchProviders();
    } catch (error) {
      if (isAxiosError(error)) {
        toast.error(String(error.response?.data?.detail || error.message));
      } else {
        toast.error(error instanceof Error ? error.message : "Failed to delete provider");
      }
    }
  }

  if (!canManage) {
    return <AccessCard description="This account cannot manage model providers." />;
  }

  return (
    <PageFrame
      title="Model Providers"
      description="Manage OpenAI-compatible providers, sync their models, test connectivity, and clean up unused entries."
      actions={
        <Button onClick={openCreateDialog}>
          <Plus className="mr-2 size-4" />
          New provider
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
                        {item.is_enabled ? "Enabled" : "Disabled"}
                      </Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4 text-sm">
                  <div>
                    <div className="mb-2 text-muted-foreground">Available models</div>
                    <div className="flex flex-wrap gap-2">
                      {item.available_models.length > 0 ? (
                        item.available_models.map((model) => (
                          <Badge key={model.id} variant="outline">
                            {model.model_name}
                          </Badge>
                        ))
                      ) : (
                        <span className="text-muted-foreground">No models registered yet.</span>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={() => void handleSyncProvider(item)}>
                      <RefreshCcw className="mr-2 size-4" />
                      Sync models
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => void handleTestProvider(item)}>
                      <Wifi className="mr-2 size-4" />
                      Test
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => openEditDialog(item)}>
                      <Pencil className="mr-2 size-4" />
                      Edit
                    </Button>
                    <Button variant="destructive" size="sm" onClick={() => void handleDeleteProvider(item)}>
                      <Trash2 className="mr-2 size-4" />
                      Delete
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit provider" : "Create provider"}</DialogTitle>
            <DialogDescription>Enter the OpenAI-compatible base URL and API key.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label htmlFor="provider-name">Name</Label>
              <Input
                id="provider-name"
                value={form.name}
                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="provider-base-url">Base URL</Label>
              <Input
                id="provider-base-url"
                value={form.base_url}
                onChange={(event) => setForm((prev) => ({ ...prev, base_url: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="provider-api-key">API key{editing ? " (leave empty to keep current value)" : ""}</Label>
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
              <span>Enable this provider</span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={isSaving || !form.name.trim() || !form.base_url.trim() || (!editing && !form.api_key.trim())}
              onClick={saveProvider}
            >
              {isSaving ? "Saving..." : editing ? "Save changes" : "Create provider"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageFrame>
  );
}
