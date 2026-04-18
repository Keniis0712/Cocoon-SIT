import { useEffect, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { isAxiosError } from "axios";
import { toast } from "sonner";

import { createChatGroup, deleteChatGroup, listChatGroups, updateChatGroup } from "@/api/chatGroups";
import type { ChatGroupPayload, ChatGroupRead } from "@/api/types";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const EMPTY_FORM: ChatGroupPayload = {
  name: "",
  description: "",
};

export default function ChatGroupsPage() {
  const [items, setItems] = useState<ChatGroupRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<ChatGroupRead | null>(null);
  const [form, setForm] = useState<ChatGroupPayload>(EMPTY_FORM);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  useEffect(() => {
    void fetchGroups();
  }, []);

  async function fetchGroups() {
    setIsLoading(true);
    try {
      const response = await listChatGroups(1, 100);
      setItems(response.items);
    } catch (error) {
      console.error(error);
      toast.error("Failed to load chat groups");
    } finally {
      setIsLoading(false);
    }
  }

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEdit(item: ChatGroupRead) {
    setEditing(item);
    setForm({ name: item.name, description: item.description || "" });
    setDialogOpen(true);
  }

  async function handleSave() {
    try {
      if (editing) {
        await updateChatGroup(editing.id, form);
        toast.success("Chat group updated");
      } else {
        await createChatGroup(form);
        toast.success("Chat group created");
      }
      setDialogOpen(false);
      await fetchGroups();
    } catch (error) {
      console.error(error);
      toast.error("Failed to save chat group");
    }
  }

  async function handleDelete(item: ChatGroupRead) {
    setDeletingId(item.id);
    try {
      await deleteChatGroup(item.id);
      toast.success("Chat group deleted");
      await fetchGroups();
    } catch (error) {
      if (isAxiosError(error)) {
        toast.error(String(error.response?.data?.detail || error.message));
      } else {
        toast.error("Failed to delete chat group");
      }
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <PageFrame
      title="Chat Groups"
      description="Manage real chat group containers used by group cocoons."
      actions={
        <Button onClick={openCreate}>
          <Plus className="mr-2 size-4" />
          New Chat Group
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
                    <CardDescription className="mt-2">{item.description || "No description"}</CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => openEdit(item)}>
                      <Pencil className="mr-2 size-4" />
                      Edit
                    </Button>
                    <Button variant="destructive" size="sm" disabled={deletingId === item.id} onClick={() => void handleDelete(item)}>
                      <Trash2 className="mr-2 size-4" />
                      Delete
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">#{item.id}</Badge>
                  <Badge variant="secondary">{item.gid}</Badge>
                </div>
                <div className="text-muted-foreground">Created: {new Date(item.created_at).toLocaleString()}</div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Chat Group" : "New Chat Group"}</DialogTitle>
            <DialogDescription>
              Group cocoons bind to these containers and use them for group tag ACL filtering.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>Name</Label>
              <Input value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>Description</Label>
              <Textarea rows={4} value={form.description || ""} onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button disabled={!form.name.trim()} onClick={() => void handleSave()}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageFrame>
  );
}
