import { useEffect, useMemo, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { showErrorToast } from "@/api/client";
import { createTag, deleteTag, listTags, updateTag } from "@/api/tags";
import type { TagPayload, TagRead } from "@/api/types/catalog";
import { useConfirmDialog } from "@/components/composes/useConfirmDialog";
import PageFrame from "@/components/PageFrame";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const EMPTY_FORM: TagPayload = {
  name: "",
  brief: "",
};

export default function TagsPage() {
  const { t } = useTranslation(["tags", "common"]);
  const [items, setItems] = useState<TagRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<TagRead | null>(null);
  const [form, setForm] = useState<TagPayload>(EMPTY_FORM);
  const { confirm, confirmDialog } = useConfirmDialog();

  const visibleItems = useMemo(() => items.filter((item) => !item.is_system), [items]);

  useEffect(() => {
    void fetchData();
  }, []);

  async function fetchData() {
    setIsLoading(true);
    try {
      setItems(await listTags());
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("tags:loadFailed"));
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
    });
    setDialogOpen(true);
  }

  async function handleSave() {
    const payload: TagPayload = {
      name: form.name.trim(),
      brief: form.brief || "",
    };
    try {
      if (editing) {
        await updateTag(editing.id, payload);
        toast.success(t("tags:updated"));
      } else {
        await createTag(payload);
        toast.success(t("tags:created"));
      }
      setDialogOpen(false);
      await fetchData();
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("tags:saveFailed"));
    }
  }

  async function handleDelete(item: TagRead) {
    const accepted = await confirm({
      title: t("tags:deleteTitle"),
      description: item.name,
      confirmLabel: t("common:delete"),
      cancelLabel: t("common:cancel"),
      variant: "destructive",
    });
    if (!accepted) {
      return;
    }
    try {
      await deleteTag(item.id);
      toast.success(t("tags:deleted"));
      await fetchData();
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("tags:deleteFailed"));
    }
  }

  return (
    <PageFrame
      title={t("tags:title")}
      description={t("tags:description")}
      actions={
        <Button onClick={openCreate}>
          <Plus className="mr-2 size-4" />
          {t("tags:newTag")}
        </Button>
      }
    >
      <div className="grid gap-4 xl:grid-cols-2">
        {isLoading ? (
          <Card className="h-48 animate-pulse bg-muted/40" />
        ) : visibleItems.length === 0 ? (
          <Card className="border-dashed border-border/70 bg-card/70">
            <CardContent className="py-10 text-sm text-muted-foreground">
              {t("tags:emptyState")}
            </CardContent>
          </Card>
        ) : (
          visibleItems.map((item) => (
            <Card key={item.actual_id} className="border-border/70 bg-card/90">
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle>{item.name}</CardTitle>
                    <CardDescription className="mt-2">
                      {item.brief || t("tags:noDescription")}
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => openEdit(item)}>
                      <Pencil className="mr-2 size-4" />
                      {t("common:edit")}
                    </Button>
                    <Button variant="destructive" size="sm" onClick={() => void handleDelete(item)}>
                      <Trash2 className="mr-2 size-4" />
                      {t("common:delete")}
                    </Button>
                  </div>
                </div>
              </CardHeader>
            </Card>
          ))
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{editing ? t("tags:editTitle") : t("tags:createTitle")}</DialogTitle>
            <DialogDescription>{t("tags:dialogDescription")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>{t("common:name")}</Label>
              <Input
                value={form.name}
                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                disabled={Boolean(editing)}
              />
            </div>
            <div className="grid gap-2">
              <Label>{t("common:description")}</Label>
              <Textarea
                rows={4}
                value={form.brief || ""}
                onChange={(event) => setForm((prev) => ({ ...prev, brief: event.target.value }))}
              />
            </div>
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
      {confirmDialog}
    </PageFrame>
  );
}
