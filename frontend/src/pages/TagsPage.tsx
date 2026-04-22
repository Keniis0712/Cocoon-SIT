import { useEffect, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { showErrorToast } from "@/api/client";
import { createTag, deleteTag, listTags, updateTag } from "@/api/tags";
import type { TagPayload, TagRead } from "@/api/types/catalog";
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
  const { t } = useTranslation();
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
      showErrorToast(error, t("tags.loadFailed"));
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
        toast.success(t("tags.updated"));
      } else {
        await createTag(payload);
        toast.success(t("tags.created"));
      }
      setDialogOpen(false);
      await fetchTags();
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("tags.saveFailed"));
    }
  }

  async function handleDelete(item: TagRead) {
    if (!window.confirm(t("tags.confirmDeletePrompt", { name: item.name }))) {
      return;
    }

    try {
      await deleteTag(item.id);
      toast.success(t("tags.deleted"));
      await fetchTags();
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("tags.deleteFailed"));
    }
  }

  return (
    <PageFrame
      title={t("tags.title")}
      description={t("tags.description")}
      actions={
        <Button onClick={openCreate}>
          <Plus className="mr-2 size-4" />
          {t("tags.newTag")}
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
                    <CardDescription className="mt-2">
                      {item.brief || t("tags.noDescription")}
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => openEdit(item)}>
                      <Pencil className="mr-2 size-4" />
                      {t("common.edit")}
                    </Button>
                    <Button variant="destructive" size="sm" onClick={() => void handleDelete(item)}>
                      <Trash2 className="mr-2 size-4" />
                      {t("common.delete")}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">
                    {t("tags.priority")}: {item.priority}
                  </Badge>
                  <Badge variant="secondary">{item.visibility_mode}</Badge>
                </div>
                <div>
                  <div className="mb-1 text-muted-foreground">{t("tags.groupAllowlist")}</div>
                  <div>{item.group_allowlist_json}</div>
                </div>
                <div>
                  <div className="mb-1 text-muted-foreground">{t("tags.groupDenylist")}</div>
                  <div>{item.group_denylist_json}</div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? t("tags.editTitle") : t("tags.createTitle")}</DialogTitle>
            <DialogDescription>{t("tags.dialogDescription")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>{t("common.name")}</Label>
              <Input value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>{t("common.description")}</Label>
              <Textarea rows={3} value={form.brief || ""} onChange={(event) => setForm((prev) => ({ ...prev, brief: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>{t("tags.visibilityMode")}</Label>
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
              <Label>{t("tags.priority")}</Label>
              <Input type="number" value={String(form.priority || 0)} onChange={(event) => setForm((prev) => ({ ...prev, priority: Number(event.target.value || 0) }))} />
            </div>
            <div className="grid gap-2">
              <Label>{t("tags.groupAllowlistInput")}</Label>
              <Input value={(form.group_allowlist || []).join(",")} onChange={(event) => setForm((prev) => ({ ...prev, group_allowlist: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) }))} />
            </div>
            <div className="grid gap-2">
              <Label>{t("tags.groupDenylistInput")}</Label>
              <Input value={(form.group_denylist || []).join(",")} onChange={(event) => setForm((prev) => ({ ...prev, group_denylist: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) }))} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button disabled={!form.name.trim()} onClick={handleSave}>
              {t("common.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageFrame>
  );
}
