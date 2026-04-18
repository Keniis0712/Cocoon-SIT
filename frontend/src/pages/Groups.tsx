import { useEffect, useMemo, useState } from "react";
import { isAxiosError } from "axios";
import { FolderTree, Plus, Trash2, UserPlus, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { listAdminUsers } from "@/api/admin-users";
import {
  addGroupMember,
  createGroup,
  deleteGroup,
  getGroupInviteSummary,
  listGroupMembers,
  listGroups,
  removeGroupMember,
  updateGroup,
} from "@/api/groups";
import type { AdminUserRead, GroupCreatePayload, GroupMemberRead, GroupRead, GroupUpdatePayload, InviteSummary } from "@/api/types";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useUserStore } from "@/store/useUserStore";

const ROOT_GROUP = "__root";

type GroupFormState = {
  name: string;
  parent_group_id: string;
  description: string;
};

const EMPTY_FORM: GroupFormState = {
  name: "",
  parent_group_id: ROOT_GROUP,
  description: "",
};

function formatTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "-";
}

export default function GroupsPage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const [groups, setGroups] = useState<GroupRead[]>([]);
  const [users, setUsers] = useState<AdminUserRead[]>([]);
  const [members, setMembers] = useState<GroupMemberRead[]>([]);
  const [summary, setSummary] = useState<InviteSummary | null>(null);
  const [selectedGroupId, setSelectedGroupId] = useState("");
  const [selectedMemberUid, setSelectedMemberUid] = useState("");
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<GroupRead | null>(null);
  const [form, setForm] = useState<GroupFormState>(EMPTY_FORM);

  const selectedGroup = useMemo(
    () => groups.find((item) => item.gid === selectedGroupId) || null,
    [groups, selectedGroupId],
  );
  const canManageSelectedGroup = Boolean(
    selectedGroup && (userInfo?.can_manage_system || selectedGroup.owner_uid === userInfo?.uid),
  );

  useEffect(() => {
    void bootstrap();
  }, [query]);

  useEffect(() => {
    if (!selectedGroupId) {
      setMembers([]);
      setSummary(null);
      return;
    }
    void loadGroupDetail(selectedGroupId);
  }, [selectedGroupId]);

  async function bootstrap() {
    setIsLoading(true);
    try {
      const [groupResponse, userResponse] = await Promise.all([
        listGroups(1, 100, { q: query.trim() || undefined }),
        listAdminUsers(1, 100),
      ]);
      setGroups(groupResponse.items);
      setUsers(userResponse.items);
      setSelectedGroupId((prev) => prev || groupResponse.items[0]?.gid || "");
    } catch (error) {
      if (isAxiosError(error)) toast.error(String(error.response?.data?.detail || error.message));
      else toast.error(t("groups.loadFailed"));
    } finally {
      setIsLoading(false);
    }
  }

  async function loadGroupDetail(gid: string) {
    try {
      const [memberResponse, summaryResponse] = await Promise.all([
        listGroupMembers(gid, 1, 100),
        getGroupInviteSummary(gid),
      ]);
      setMembers(memberResponse.items);
      setSummary(summaryResponse);
      const firstCandidate = users.find((item) => !memberResponse.items.some((member) => member.user_uid === item.uid));
      setSelectedMemberUid(firstCandidate?.uid || "");
    } catch (error) {
      if (isAxiosError(error)) toast.error(String(error.response?.data?.detail || error.message));
      else toast.error(t("groups.detailLoadFailed"));
    }
  }

  function openCreateDialog() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEditDialog(group: GroupRead) {
    setEditing(group);
    setForm({
      name: group.name,
      parent_group_id: group.parent_group_id || ROOT_GROUP,
      description: group.description || "",
    });
    setDialogOpen(true);
  }

  async function saveGroup() {
    setIsSaving(true);
    try {
      if (editing) {
        const payload: GroupUpdatePayload = {
          name: form.name.trim(),
          parent_group_id: form.parent_group_id === ROOT_GROUP ? null : form.parent_group_id,
          description: form.description.trim() || null,
        };
        await updateGroup(editing.gid, payload);
        toast.success(t("groups.updated"));
      } else {
        const payload: GroupCreatePayload = {
          name: form.name.trim(),
          parent_group_id: form.parent_group_id === ROOT_GROUP ? null : form.parent_group_id,
          description: form.description.trim() || null,
        };
        await createGroup(payload);
        toast.success(t("groups.created"));
      }
      setDialogOpen(false);
      setEditing(null);
      await bootstrap();
    } catch (error) {
      if (isAxiosError(error)) toast.error(String(error.response?.data?.detail || error.message));
      else toast.error(t("groups.saveFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDeleteGroup() {
    if (!selectedGroup) {
      return;
    }
    try {
      await deleteGroup(selectedGroup.gid);
      toast.success(t("groups.deleted"));
      setSelectedGroupId("");
      await bootstrap();
    } catch (error) {
      if (isAxiosError(error)) toast.error(String(error.response?.data?.detail || error.message));
      else toast.error(t("groups.deleteFailed"));
    }
  }

  async function handleAddMember() {
    if (!selectedGroup || !selectedMemberUid) {
      return;
    }
    try {
      await addGroupMember(selectedGroup.gid, selectedMemberUid);
      toast.success(t("groups.memberAdded"));
      await loadGroupDetail(selectedGroup.gid);
    } catch (error) {
      if (isAxiosError(error)) toast.error(String(error.response?.data?.detail || error.message));
      else toast.error(t("groups.memberAddFailed"));
    }
  }

  async function handleRemoveMember(userUid: string) {
    if (!selectedGroup) {
      return;
    }
    try {
      await removeGroupMember(selectedGroup.gid, userUid);
      toast.success(t("groups.memberRemoved"));
      await loadGroupDetail(selectedGroup.gid);
    } catch (error) {
      if (isAxiosError(error)) toast.error(String(error.response?.data?.detail || error.message));
      else toast.error(t("groups.memberRemoveFailed"));
    }
  }

  const availableMemberOptions = users.filter((item) => !members.some((member) => member.user_uid === item.uid));

  return (
    <PageFrame
      title={t("groups.title")}
      description={t("groups.description")}
      actions={
        <Button onClick={openCreateDialog}>
          <Plus className="mr-2 size-4" />
          {t("groups.newGroup")}
        </Button>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.25fr]">
        <div className="space-y-4">
          <Card className="border-border/70 bg-card/90">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <FolderTree className="size-4 text-primary" />
                {t("groups.list")}
              </CardTitle>
              <CardDescription>{t("groups.listDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-2">
                <Label>{t("common.keyword")}</Label>
                <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("groups.keywordPlaceholder")} />
              </div>
              {isLoading ? (
                <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("common.loading")}</div>
              ) : groups.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("groups.empty")}</div>
              ) : (
                groups.map((group) => (
                  <button
                    key={group.gid}
                    type="button"
                    onClick={() => setSelectedGroupId(group.gid)}
                    className={`w-full rounded-2xl border p-4 text-left transition ${selectedGroupId === group.gid ? "border-primary bg-primary/5" : "border-border/70 hover:border-primary/40 hover:bg-accent/40"}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-medium">{group.name}</div>
                        <div className="mt-1 break-all text-xs text-muted-foreground">{group.gid}</div>
                      </div>
                      <Badge variant="outline">{group.parent_group_id || t("groups.rootGroup")}</Badge>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge variant="secondary">{t("groups.ownerUid")}: {group.owner_uid}</Badge>
                      <Badge variant="outline">
                        {group.invite_quota_unlimited ? t("groups.unlimitedQuota") : `${t("groups.inviteQuota")}: ${group.invite_quota_remaining}`}
                      </Badge>
                    </div>
                  </button>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card className="border-border/70 bg-card/90">
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-base">{selectedGroup?.name || t("groups.noSelectionTitle")}</CardTitle>
                  <CardDescription>{selectedGroup?.description || t("groups.noSelectionDescription")}</CardDescription>
                </div>
                {selectedGroup && canManageSelectedGroup ? (
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={() => openEditDialog(selectedGroup)}>
                      {t("common.edit")}
                    </Button>
                    <Button variant="destructive" size="sm" onClick={() => void handleDeleteGroup()}>
                      <Trash2 className="mr-2 size-4" />
                      {t("common.delete")}
                    </Button>
                  </div>
                ) : null}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {selectedGroup ? (
                <>
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <div className="rounded-2xl border border-border/70 p-4 text-sm">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("groups.ownerUid")}</div>
                      <div className="mt-2 break-all font-medium">{selectedGroup.owner_uid}</div>
                    </div>
                    <div className="rounded-2xl border border-border/70 p-4 text-sm">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("groups.parentGroup")}</div>
                      <div className="mt-2 break-all font-medium">{selectedGroup.parent_group_id || t("groups.rootGroup")}</div>
                    </div>
                    <div className="rounded-2xl border border-border/70 p-4 text-sm">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("groups.groupPath")}</div>
                      <div className="mt-2 break-all font-medium">{selectedGroup.group_path}</div>
                    </div>
                    <div className="rounded-2xl border border-border/70 p-4 text-sm">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("groups.updatedAt")}</div>
                      <div className="mt-2 font-medium">{formatTime(selectedGroup.updated_at)}</div>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-border/70 p-4 text-sm">
                    <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{t("groups.inviteSummary")}</div>
                    <div className="font-medium">
                      {summary?.invite_quota_unlimited ? t("groups.unlimitedQuota") : `${summary?.invite_quota_remaining ?? 0}`}
                    </div>
                  </div>
                </>
              ) : (
                <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("groups.noSelection")}</div>
              )}
            </CardContent>
          </Card>

          <Card className="border-border/70 bg-card/90">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Users className="size-4 text-primary" />
                {t("groups.membersTitle")}
              </CardTitle>
              <CardDescription>{t("groups.membersDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {selectedGroup && canManageSelectedGroup ? (
                <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
                  <div className="grid gap-2">
                    <Label>{t("groups.addMember")}</Label>
                    <Select value={selectedMemberUid} onValueChange={setSelectedMemberUid}>
                      <SelectTrigger><SelectValue placeholder={t("groups.selectUser")} /></SelectTrigger>
                      <SelectContent>
                        {availableMemberOptions.map((item) => (
                          <SelectItem key={item.uid} value={item.uid}>
                            {item.username} · {item.uid}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <Button disabled={!selectedMemberUid} onClick={() => void handleAddMember()}>
                    <UserPlus className="mr-2 size-4" />
                    {t("groups.addMember")}
                  </Button>
                </div>
              ) : null}

              {selectedGroup ? (
                members.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("groups.noMembers")}</div>
                ) : (
                  members.map((member) => (
                    <div key={member.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border/70 p-4 text-sm">
                      <div>
                        <div className="font-medium">{member.user_uid}</div>
                        <div className="mt-1 text-muted-foreground">{formatTime(member.created_at)}</div>
                      </div>
                      {canManageSelectedGroup ? (
                        <Button variant="ghost" size="sm" onClick={() => void handleRemoveMember(member.user_uid)}>
                          <Trash2 className="mr-2 size-4" />
                          {t("common.delete")}
                        </Button>
                      ) : null}
                    </div>
                  ))
                )
              ) : (
                <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("groups.noSelection")}</div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{editing ? t("groups.editGroup") : t("groups.newGroup")}</DialogTitle>
            <DialogDescription>{t("groups.dialogDescription")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>{t("common.name")}</Label>
              <Input value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>{t("groups.parentGroup")}</Label>
              <Select value={form.parent_group_id} onValueChange={(value) => setForm((prev) => ({ ...prev, parent_group_id: value }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={ROOT_GROUP}>{t("groups.rootGroup")}</SelectItem>
                  {groups
                    .filter((group) => !editing || group.gid !== editing.gid)
                    .map((group) => (
                      <SelectItem key={group.gid} value={group.gid}>
                        {group.name} · {group.gid}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>{t("common.description")}</Label>
              <Textarea rows={4} value={form.description} onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>{t("common.cancel")}</Button>
            <Button disabled={isSaving || !form.name.trim()} onClick={() => void saveGroup()}>
              {isSaving ? t("common.saving") : t("common.saveChanges")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageFrame>
  );
}
