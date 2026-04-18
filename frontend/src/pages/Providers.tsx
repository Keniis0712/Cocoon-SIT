import { useEffect, useMemo, useState } from "react";
import { isAxiosError } from "axios";
import { CirclePlay, Pencil, Plus, RefreshCw, Server, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { createModelProvider, deleteModelProvider, listModelProviders, syncModelProvider, testModelProvider, updateModelProvider } from "@/api/providers";
import type { ModelProviderPayload, ModelProviderRead, ModelProviderTestResponse } from "@/api/types";
import AccessCard from "@/components/AccessCard";
import PageFrame from "@/components/PageFrame";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
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
  const [deleting, setDeleting] = useState<ModelProviderRead | null>(null);
  const [form, setForm] = useState<ModelProviderPayload>(EMPTY_FORM);
  const [testing, setTesting] = useState<ModelProviderRead | null>(null);
  const [testModelId, setTestModelId] = useState<string>("");
  const [testPrompt, setTestPrompt] = useState("你好，请做一个简短自我介绍。");
  const [testResult, setTestResult] = useState<ModelProviderTestResponse | null>(null);
  const [isTesting, setIsTesting] = useState(false);

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
      fetchProviders();
    }
  }, [canManage]);

  const testModels = useMemo(() => testing?.available_models || [], [testing]);

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
        toast.success("提供方已更新");
      } else {
        await createModelProvider({
          name: payload.name || "",
          base_url: payload.base_url || "",
          api_key: payload.api_key || "",
          is_enabled: payload.is_enabled ?? true,
        });
        toast.success("提供方已创建");
      }

      setDialogOpen(false);
      setEditing(null);
      setForm(EMPTY_FORM);
      await fetchProviders();
    } catch (error) {
      if (isAxiosError(error)) {
        toast.error(String(error.response?.data?.detail || error.message));
      } else {
        toast.error("保存提供方失败");
      }
    } finally {
      setIsSaving(false);
    }
  }

  async function runSync(providerId: number) {
    try {
      await syncModelProvider(providerId);
      toast.success("模型列表已同步");
      await fetchProviders();
    } catch (error) {
      if (isAxiosError(error)) {
        toast.error(String(error.response?.data?.detail || error.message));
      } else {
        toast.error("同步失败");
      }
    }
  }

  async function runDelete() {
    if (!deleting) {
      return;
    }

    try {
      await deleteModelProvider(deleting.id);
      toast.success("提供方已删除");
      setDeleting(null);
      await fetchProviders();
    } catch (error) {
      if (isAxiosError(error)) {
        toast.error(String(error.response?.data?.detail || error.message));
      } else {
        toast.error("删除提供方失败");
      }
    }
  }

  async function runTest() {
    if (!testing || !testModelId) {
      return;
    }

    setIsTesting(true);
    try {
      const result = await testModelProvider(testing.id, {
        selected_model_id: Number(testModelId),
        prompt: testPrompt,
      });
      setTestResult(result);
      toast.success("模型测试完成");
    } catch (error) {
      if (isAxiosError(error)) {
        toast.error(String(error.response?.data?.detail || error.message));
      } else {
        toast.error("模型测试失败");
      }
    } finally {
      setIsTesting(false);
    }
  }

  if (!canManage) {
    return <AccessCard description="当前账号没有管理模型提供方的权限。" />;
  }

  return (
    <PageFrame
      title="模型提供方"
      description="维护 OpenAI-compatible 提供方，并同步、测试可用模型。"
      actions={
        <Button onClick={openCreateDialog}>
          <Plus className="mr-2 size-4" />
          新建提供方
        </Button>
      }
    >
      <div className="grid gap-4 xl:grid-cols-2">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, index) => (
            <Card key={index} className="h-64 animate-pulse bg-muted/40" />
          ))
        ) : (
          items.map((item) => (
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
                    <Badge variant={item.is_enabled ? "default" : "secondary"}>{item.is_enabled ? "已启用" : "已停用"}</Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <div>
                  <div className="mb-2 text-muted-foreground">可用模型</div>
                  <div className="flex flex-wrap gap-2">
                    {item.available_models.length > 0 ? (
                      item.available_models.map((model) => (
                        <Badge key={model.id} variant="outline">{model.model_name}</Badge>
                      ))
                    ) : (
                      <span className="text-muted-foreground">暂无模型，请先同步。</span>
                    )}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={() => runSync(item.id)}>
                    <RefreshCw className="mr-2 size-4" />
                    同步模型
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => { setTesting(item); setTestModelId(String(item.available_models[0]?.id || "")); setTestResult(null); }}>
                    <CirclePlay className="mr-2 size-4" />
                    测试模型
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => openEditDialog(item)}>
                    <Pencil className="mr-2 size-4" />
                    编辑
                  </Button>
                  <Button variant="destructive" size="sm" onClick={() => setDeleting(item)}>
                    <Trash2 className="mr-2 size-4" />
                    删除
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? "编辑模型提供方" : "新建模型提供方"}</DialogTitle>
            <DialogDescription>请填写兼容 OpenAI 的 base URL 和 API key。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label htmlFor="provider-name">名称</Label>
              <Input id="provider-name" value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="provider-base-url">Base URL</Label>
              <Input id="provider-base-url" value={form.base_url} onChange={(event) => setForm((prev) => ({ ...prev, base_url: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="provider-api-key">API Key{editing ? "（留空则不修改）" : ""}</Label>
              <Input id="provider-api-key" type="password" value={form.api_key} onChange={(event) => setForm((prev) => ({ ...prev, api_key: event.target.value }))} />
            </div>
            <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
              <Checkbox checked={form.is_enabled} onCheckedChange={(checked) => setForm((prev) => ({ ...prev, is_enabled: Boolean(checked) }))} />
              <span>启用该提供方</span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>取消</Button>
            <Button disabled={isSaving || !form.name.trim() || !form.base_url.trim() || (!editing && !form.api_key.trim())} onClick={saveProvider}>
              {isSaving ? "保存中..." : editing ? "保存修改" : "创建提供方"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(testing)} onOpenChange={(open) => !open && (setTesting(null), setTestResult(null))}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>测试模型</DialogTitle>
            <DialogDescription>先选择一个已同步模型，再发送一段测试 Prompt。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>模型</Label>
              <Select value={testModelId} onValueChange={setTestModelId}>
                <SelectTrigger>
                  <SelectValue placeholder="选择模型" />
                </SelectTrigger>
                <SelectContent>
                  {testModels.map((model) => (
                    <SelectItem key={model.id} value={String(model.id)}>{model.model_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>测试 Prompt</Label>
              <Textarea rows={4} value={testPrompt} onChange={(event) => setTestPrompt(event.target.value)} />
            </div>
            {testResult ? (
              <div className="grid gap-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">模型回复</CardTitle>
                  </CardHeader>
                  <CardContent className="whitespace-pre-wrap text-sm">{testResult.reply}</CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">结构化测试结果</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {testResult.structured_tests.map((item) => (
                      <div key={item.name} className="rounded-lg border border-border/70 p-3">
                        <div className="mb-2 font-medium">{item.name}</div>
                        <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(item.parsed_result, null, 2)}</pre>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setTesting(null); setTestResult(null); }}>关闭</Button>
            <Button disabled={isTesting || !testModelId || !testPrompt.trim()} onClick={runTest}>
              {isTesting ? "测试中..." : "开始测试"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => !open && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除提供方？</AlertDialogTitle>
            <AlertDialogDescription>如果已有 Cocoon 在使用该提供方，后端会拒绝删除。</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={runDelete}>继续删除</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageFrame>
  );
}
