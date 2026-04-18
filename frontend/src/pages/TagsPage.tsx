import { useEffect, useState } from "react";
import { Pencil, Plus } from "lucide-react";
import { toast } from "sonner";

import { createTag, listTags, updateTag } from "@/api/tags";
import type { TagPayload, TagRead } from "@/api/types";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const EMPTY_FORM: TagPayload = {
  name: "",
  brief: "",
  priority: 10_000,
  visibility_mode: "private",
  group_allowlist: [],
  group_denylist: [],
};

export default function TagsPage() {
  const [items, setItems] = useState<TagRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<TagRead | null>(null);
  const [form, setForm] = useState<TagPayload>(EMPTY_FORM);

  useEffect(() => {
    void fetchTags();
  }, []);

  async function fetchTags() {
    setIsLoading(true);
    try {
      setItems(await listTags());
    } catch (error) {
      console.error(error);
      toast.error("加载标签失败");
    } finally {
      setIsLoading(false);
    }
  }

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEdit(item: TagRead) {
    setEditing(item);
    setForm({
      name: item.name,
      brief: item.brief,
      priority: item.priority,
      visibility_mode: item.visibility_mode,
      group_allowlist: JSON.parse(item.group_allowlist_json || "[]"),
      group_denylist: JSON.parse(item.group_denylist_json || "[]"),
    });
    setDialogOpen(true);
  }

  async function handleSave() {
    const payload: TagPayload = {
      name: form.name.trim(),
      brief: form.brief || "",
      priority: form.priority || 0,
      visibility_mode: form.visibility_mode || "private",
      group_allowlist: form.group_allowlist || [],
      group_denylist: form.group_denylist || [],
    };
    try {
      if (editing) {
        await updateTag(editing.id, payload);
        toast.success("标签已更新");
      } else {
        await createTag(payload);
        toast.success("标签已创建");
      }
      setDialogOpen(false);
      await fetchTags();
    } catch (error) {
      console.error(error);
      toast.error("保存标签失败");
    }
  }

  return (
    <PageFrame
      title="标签"
      description="维护动态语义标签，供 Cocoon、消息与长期记忆使用。"
      actions={
        <Button onClick={openCreate}>
          <Plus className="mr-2 size-4" />
          新建标签
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
                    <CardDescription className="mt-2">{item.brief || "暂无说明"}</CardDescription>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => openEdit(item)}>
                    <Pencil className="mr-2 size-4" />
                    编辑
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">优先级 {item.priority}</Badge>
                  <Badge variant="secondary">{item.visibility_mode}</Badge>
                </div>
                <div>
                  <div className="mb-1 text-muted-foreground">允许群</div>
                  <div className="text-sm">{item.group_allowlist_json}</div>
                </div>
                <div>
                  <div className="mb-1 text-muted-foreground">拒绝群</div>
                  <div className="text-sm">{item.group_denylist_json}</div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "编辑标签" : "新建标签"}</DialogTitle>
            <DialogDescription>标签决定 Bubble / Deep Sea 检索时的可见范围。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>名称</Label>
              <Input value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>说明</Label>
              <Textarea rows={3} value={form.brief || ""} onChange={(event) => setForm((prev) => ({ ...prev, brief: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>可见性</Label>
              <Select value={form.visibility_mode} onValueChange={(value) => setForm((prev) => ({ ...prev, visibility_mode: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="private">private</SelectItem>
                  <SelectItem value="public">public</SelectItem>
                  <SelectItem value="group_acl">group_acl</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>优先级</Label>
              <Input type="number" value={String(form.priority || 0)} onChange={(event) => setForm((prev) => ({ ...prev, priority: Number(event.target.value || 0) }))} />
            </div>
            <div className="grid gap-2">
              <Label>允许群（逗号分隔 gid）</Label>
              <Input value={(form.group_allowlist || []).join(",")} onChange={(event) => setForm((prev) => ({ ...prev, group_allowlist: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) }))} />
            </div>
            <div className="grid gap-2">
              <Label>拒绝群（逗号分隔 gid）</Label>
              <Input value={(form.group_denylist || []).join(",")} onChange={(event) => setForm((prev) => ({ ...prev, group_denylist: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) }))} />
            </div>
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
