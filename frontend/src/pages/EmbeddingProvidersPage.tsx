import { useEffect, useState } from "react";
import { Pencil, Plus } from "lucide-react";
import { toast } from "sonner";

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
      toast.error("加载 Embedding 提供方失败");
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
        toast.success("Embedding 提供方已更新");
      } else {
        await createEmbeddingProvider(form);
        toast.success("Embedding 提供方已创建");
      }
      setDialogOpen(false);
      await fetchItems();
    } catch (error) {
      console.error(error);
      toast.error("保存 Embedding 提供方失败");
    }
  }

  return (
    <PageFrame
      title="Embedding Providers"
      description="配置本地 CPU 或 OpenAI-compatible embedding 服务。可保留多条配置，但同一时间只会有一个启用项。"
      actions={
        <Button onClick={openCreate}>
          <Plus className="mr-2 size-4" />
          新建 Embedding 提供方
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
                    编辑
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex flex-wrap gap-2">
                  {item.is_default ? <Badge>默认</Badge> : null}
                  <Badge variant={item.is_enabled ? "default" : "secondary"}>
                    {item.is_enabled ? "启用" : "停用"}
                  </Badge>
                </div>
                <div className="text-muted-foreground">Base URL：{item.base_url || "-"}</div>
                <div className="text-muted-foreground">远端模型：{item.model_name || "-"}</div>
                <div className="text-muted-foreground">本地模型：{item.local_model_name || "-"}</div>
                <div className="text-muted-foreground">设备：{item.device}</div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
            <DialogHeader>
              <DialogTitle>{editing ? "编辑 Embedding 提供方" : "新建 Embedding 提供方"}</DialogTitle>
            <DialogDescription>远端模式需要 OpenAI-compatible endpoint；本地模式默认走 CPU。启用当前项时，后端会自动停用其它 Embedding 提供方。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>名称</Label>
              <Input value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>类型</Label>
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
              <Label>Base URL</Label>
              <Input value={form.base_url || ""} onChange={(event) => setForm((prev) => ({ ...prev, base_url: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>API Key</Label>
              <Input type="password" value={form.api_key || ""} onChange={(event) => setForm((prev) => ({ ...prev, api_key: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>远端模型</Label>
              <Input value={form.model_name || ""} onChange={(event) => setForm((prev) => ({ ...prev, model_name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>本地模型</Label>
              <Input value={form.local_model_name || ""} onChange={(event) => setForm((prev) => ({ ...prev, local_model_name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>设备</Label>
              <Input value={form.device || "cpu"} onChange={(event) => setForm((prev) => ({ ...prev, device: event.target.value }))} />
            </div>
            <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
              <Checkbox checked={form.is_enabled} onCheckedChange={(checked) => setForm((prev) => ({ ...prev, is_enabled: Boolean(checked) }))} />
              <span>启用该 Embedding 提供方</span>
            </label>
            <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
              <Checkbox checked={form.is_default} onCheckedChange={(checked) => setForm((prev) => ({ ...prev, is_default: Boolean(checked) }))} />
              <span>设为默认</span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>取消</Button>
            <Button disabled={!form.name.trim()} onClick={handleSave}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageFrame>
  );
}
