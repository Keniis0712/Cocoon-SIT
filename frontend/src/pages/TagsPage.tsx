import { useEffect, useMemo, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { showErrorToast } from "@/api/client";
import { listChatGroups } from "@/api/chatGroups";
import { createTag, deleteTag, listTags, updateTag } from "@/api/tags";
import type { TagPayload, TagRead } from "@/api/types/catalog";
import type { ChatGroupRead } from "@/api/types/chat-groups";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const EMPTY_FORM: TagPayload = {
  name: "",
  brief: "",
  visibility_mode: "private",
  visible_chat_group_ids: [],
};

export default function TagsPage() {
  const [items, setItems] = useState<TagRead[]>([]);
  const [rooms, setRooms] = useState<ChatGroupRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<TagRead | null>(null);
  const [form, setForm] = useState<TagPayload>(EMPTY_FORM);

  const visibleItems = useMemo(() => items.filter((item) => !item.is_system), [items]);

  useEffect(() => {
    void fetchData();
  }, []);

  async function fetchData() {
    setIsLoading(true);
    try {
      const [tagItems, roomItems] = await Promise.all([listTags(), listChatGroups()]);
      setItems(tagItems);
      setRooms(roomItems);
    } catch (error) {
      console.error(error);
      showErrorToast(error, "Failed to load tags");
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
      visibility_mode: item.visibility_mode,
      visible_chat_group_ids: item.visible_chat_group_ids,
    });
    setDialogOpen(true);
  }

  async function handleSave() {
    const payload: TagPayload = {
      name: form.name.trim(),
      brief: form.brief || "",
      visibility_mode: form.visibility_mode || "private",
      visible_chat_group_ids: form.visibility_mode === "group_acl" ? form.visible_chat_group_ids || [] : [],
    };
    try {
      if (editing) {
        await updateTag(editing.id, payload);
        toast.success("Tag updated");
      } else {
        await createTag(payload);
        toast.success("Tag created");
      }
      setDialogOpen(false);
      await fetchData();
    } catch (error) {
      console.error(error);
      showErrorToast(error, "Failed to save tag");
    }
  }

  async function handleDelete(item: TagRead) {
    if (!window.confirm(`Delete tag "${item.name}"?`)) {
      return;
    }
    try {
      await deleteTag(item.id);
      toast.success("Tag deleted");
      await fetchData();
    } catch (error) {
      console.error(error);
      showErrorToast(error, "Failed to delete tag");
    }
  }

  function toggleRoom(roomId: string, checked: boolean) {
    const current = new Set(form.visible_chat_group_ids || []);
    if (checked) {
      current.add(roomId);
    } else {
      current.delete(roomId);
    }
    setForm((prev) => ({ ...prev, visible_chat_group_ids: [...current] }));
  }

  return (
    <PageFrame
      title="Tags"
      description="Manage canonical runtime tags and chat-group visibility."
      actions={
        <Button onClick={openCreate}>
          <Plus className="mr-2 size-4" />
          New Tag
        </Button>
      }
    >
      <div className="grid gap-4 xl:grid-cols-2">
        {isLoading ? (
          <Card className="h-48 animate-pulse bg-muted/40" />
        ) : (
          visibleItems.map((item) => (
            <Card key={item.actual_id} className="border-border/70 bg-card/90">
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle>{item.name}</CardTitle>
                    <CardDescription className="mt-2">
                      {item.brief || "No description"}
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => openEdit(item)}>
                      <Pencil className="mr-2 size-4" />
                      Edit
                    </Button>
                    <Button variant="destructive" size="sm" onClick={() => void handleDelete(item)}>
                      <Trash2 className="mr-2 size-4" />
                      Delete
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">{item.visibility_mode}</Badge>
                </div>
                {item.visibility_mode === "group_acl" ? (
                  <div>
                    <div className="mb-1 text-muted-foreground">Visible Chat Groups</div>
                    <div className="flex flex-wrap gap-2">
                      {item.visible_chat_group_ids.length
                        ? item.visible_chat_group_ids.map((roomId) => {
                            const room = rooms.find((entry) => entry.id === roomId);
                            return (
                              <Badge key={roomId} variant="outline">
                                {room?.name || roomId}
                              </Badge>
                            );
                          })
                        : <span className="text-muted-foreground">No rooms selected</span>}
                    </div>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ))
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Tag" : "Create Tag"}</DialogTitle>
            <DialogDescription>
              Runtime tags are stored by canonical id. Models can only reference them by the numbered tag catalog exposed in prompts.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>Name</Label>
              <Input
                value={form.name}
                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                disabled={Boolean(editing)}
              />
            </div>
            <div className="grid gap-2">
              <Label>Description</Label>
              <Textarea
                rows={3}
                value={form.brief || ""}
                onChange={(event) => setForm((prev) => ({ ...prev, brief: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label>Visibility</Label>
              <Select
                value={form.visibility_mode}
                onValueChange={(value) => setForm((prev) => ({ ...prev, visibility_mode: value }))}
              >
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
            {form.visibility_mode === "group_acl" ? (
              <div className="grid gap-2">
                <Label>Visible Chat Groups</Label>
                <div className="max-h-64 space-y-2 overflow-auto rounded-2xl border border-border/70 bg-background/60 p-3">
                  {rooms.length ? (
                    rooms.map((room) => {
                      const checked = (form.visible_chat_group_ids || []).includes(room.id);
                      return (
                        <label key={room.id} className="flex items-center gap-3 text-sm">
                          <Checkbox checked={checked} onCheckedChange={(value) => toggleRoom(room.id, Boolean(value))} />
                          <span>{room.name}</span>
                        </label>
                      );
                    })
                  ) : (
                    <span className="text-sm text-muted-foreground">No chat groups available.</span>
                  )}
                </div>
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button disabled={!form.name.trim()} onClick={handleSave}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageFrame>
  );
}
