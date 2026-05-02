import { useEffect, useMemo, useState } from "react";
import { Globe2, LockKeyhole, Pencil, Plus, ShieldCheck, Trash2, UserRound } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { listAdminUsers } from "@/api/admin-users";
import { showErrorToast } from "@/api/client";
import {
  appendCharacterAclEntries,
  deleteCharacter,
  deleteCharacterAclEntry,
  getCharacterAcl,
  getCharacterEffectiveAcl,
  getCharacters,
  createCharacter,
  updateCharacter,
} from "@/api/characters";
import { listGroups } from "@/api/groups";
import type { AdminUserRead, GroupRead } from "@/api/types/access";
import type {
  CharacterAclEffectiveEntry,
  CharacterAclEntryRead,
  CharacterAclEntryWrite,
  CharacterPayload,
  CharacterRead,
} from "@/api/types/catalog";
import AccessCard from "@/components/AccessCard";
import { PopupSelect } from "@/components/composes/PopupSelect";
import { useConfirmDialog } from "@/components/composes/useConfirmDialog";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useUserStore } from "@/store/useUserStore";

const AUTHENTICATED_KEY = "authenticated";

const EMPTY_FORM: CharacterPayload = {
  name: "",
  description: "",
  personality_prompt: "",
  visibility: "private",
};

type CharacterTab = "visible" | "manage";
type VisibleScopeMode = "basic_visible" | "inherited_visible";
type EffectiveQueryMode = "user" | "group";
type AclDraftEntry = CharacterAclEntryWrite & { localId: string };

function permissionLabel(level: string | number, t: (key: string) => string) {
  if (typeof level === "number") {
    return level >= 3
      ? t("characters.permissionManage")
      : level >= 2
        ? t("characters.permissionUse")
        : t("characters.permissionRead");
  }
  if (level === "MANAGE") return t("characters.permissionManage");
  if (level === "USE") return t("characters.permissionUse");
  return t("characters.permissionRead");
}

function subjectTypeLabel(type: string, t: (key: string) => string) {
  if (type === "USER") return t("characters.granteeUser");
  if (type === "GROUP") return t("characters.granteeGroup");
  if (type === "SUBTREE") return t("characters.granteeSubtree");
  if (type === "AUTHENTICATED_ALL") return t("characters.authenticatedAll");
  return type;
}

export default function CharactersPage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const [items, setItems] = useState<CharacterRead[]>([]);
  const [manageableIds, setManageableIds] = useState<Set<number>>(new Set());
  const [page, setPage] = useState(1);
  const [pageSize] = useState(12);
  const [totalPages, setTotalPages] = useState(1);
  const [tab, setTab] = useState<CharacterTab>("visible");
  const [visibleScope, setVisibleScope] = useState<VisibleScopeMode>("basic_visible");
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<CharacterRead | null>(null);
  const [form, setForm] = useState<CharacterPayload>(EMPTY_FORM);

  const [aclOpen, setAclOpen] = useState(false);
  const [aclCharacter, setAclCharacter] = useState<CharacterRead | null>(null);
  const [existingAclEntries, setExistingAclEntries] = useState<CharacterAclEntryRead[]>([]);
  const [aclDrafts, setAclDrafts] = useState<AclDraftEntry[]>([]);
  const [aclUsers, setAclUsers] = useState<AdminUserRead[]>([]);
  const [aclGroups, setAclGroups] = useState<GroupRead[]>([]);
  const [effectiveMode, setEffectiveMode] = useState<EffectiveQueryMode>("user");
  const [effectiveTarget, setEffectiveTarget] = useState("");
  const [effectiveItems, setEffectiveItems] = useState<CharacterAclEffectiveEntry[]>([]);
  const [effectiveLoading, setEffectiveLoading] = useState(false);
  const { confirm, confirmDialog } = useConfirmDialog();

  const canManageSystem = Boolean(userInfo?.can_manage_system);
  const canShowManagementTab = Boolean(userInfo?.has_management_console || userInfo?.is_bootstrap_admin);

  async function fetchData() {
    setIsLoading(true);
    try {
      const activeScope = tab === "manage" ? "manageable" : visibleScope;
      const [response, manageableResponse] = await Promise.all([
        getCharacters(page, pageSize, activeScope),
        getCharacters(1, 200, "manageable"),
      ]);
      setItems(response.items);
      setTotalPages(response.total_pages || 1);
      setManageableIds(new Set(manageableResponse.items.map((item) => item.id)));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void fetchData();
  }, [page, tab, visibleScope]);

  const filteredItems = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) {
      return items;
    }
    return items.filter((item) => {
      const haystack = [item.name, item.description || "", item.owner_uid || "", item.personality_prompt]
        .join("\n")
        .toLowerCase();
      return haystack.includes(keyword);
    });
  }, [items, query]);

  const visibleCountText = useMemo(() => {
    if (filteredItems.length === 0) {
      return t("characters.emptyStats");
    }
    return t("characters.pageStats", { page, totalPages, count: filteredItems.length });
  }, [filteredItems.length, page, t, totalPages]);

  const userLabels = useMemo(
    () => new Map(aclUsers.map((item) => [item.uid, `${item.username} / ${item.uid}`])),
    [aclUsers],
  );
  const groupLabels = useMemo(
    () => new Map(aclGroups.map((item) => [item.gid, `${item.name} / ${item.gid}`])),
    [aclGroups],
  );
  const aclUserOptions = useMemo(
    () =>
      aclUsers.map((item) => ({
        value: item.uid,
        label: item.username,
        description: item.uid,
        keywords: [item.email || ""],
      })),
    [aclUsers],
  );
  const aclGroupOptions = useMemo(
    () =>
      aclGroups.map((group) => ({
        value: group.gid,
        label: group.name,
        description: group.group_path || group.gid,
        keywords: [group.gid],
      })),
    [aclGroups],
  );

  function formatAclTarget(entry: { grantee_id: string | null; grantee_type?: string; source?: string }) {
    const subjectType = entry.grantee_type ?? entry.source ?? "";
    if (!entry.grantee_id || subjectType === "AUTHENTICATED_ALL") {
      return t("characters.authenticatedAll");
    }
    if (subjectType === "USER" || subjectType === "SUBTREE") {
      return userLabels.get(entry.grantee_id) || entry.grantee_id;
    }
    if (subjectType === "GROUP") {
      return groupLabels.get(entry.grantee_id) || entry.grantee_id;
    }
    return entry.grantee_id;
  }

  function openCreateDialog() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEditDialog(item: CharacterRead) {
    setEditing(item);
    setForm({
      name: item.name,
      description: item.description || "",
      personality_prompt: item.personality_prompt,
      visibility: item.visibility === "public" ? "public" : "private",
    });
    setDialogOpen(true);
  }

  async function saveCharacter() {
    setIsSaving(true);
    try {
      const payload: CharacterPayload = {
        name: form.name.trim(),
        description: form.description?.trim() || null,
        personality_prompt: form.personality_prompt.trim(),
        visibility: canManageSystem ? form.visibility : "private",
      };

      if (editing) {
        await updateCharacter(editing.id, payload);
        toast.success(t("characters.updated"));
      } else {
        await createCharacter(payload);
        toast.success(t("characters.created"));
      }

      setDialogOpen(false);
      setEditing(null);
      setForm(EMPTY_FORM);
      await fetchData();
    } catch (error) {
      showErrorToast(error, t("characters.saveFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  async function openAclDialog(item: CharacterRead) {
    setAclOpen(true);
    setAclCharacter(item);
    setExistingAclEntries([]);
    setAclDrafts([]);
    setEffectiveItems([]);
    setEffectiveTarget(userInfo?.uid || "");
    setEffectiveMode("user");
    try {
      const [aclResponse, usersResponse, groupsResponse] = await Promise.all([
        getCharacterAcl(item.id),
        listAdminUsers(1, 100),
        listGroups(1, 100),
      ]);
      setExistingAclEntries(aclResponse);
      setAclUsers(usersResponse.items);
      setAclGroups(groupsResponse.items);
    } catch (error) {
      setAclOpen(false);
      showErrorToast(error, t("characters.aclLoadFailed"));
    }
  }

  function addAclDraft() {
    setAclDrafts((prev) => [
      ...prev,
      {
        localId: `${Date.now()}-${prev.length}`,
        grantee_type: "USER",
        grantee_id: userInfo?.uid || "",
        perm_level: "READ",
      },
    ]);
  }

  function updateAclDraft(localId: string, patch: Partial<AclDraftEntry>) {
    setAclDrafts((prev) =>
      prev.map((item) => {
        if (item.localId !== localId) {
          return item;
        }
        const next = { ...item, ...patch };
        if (next.grantee_type === "AUTHENTICATED_ALL") {
          next.grantee_id = AUTHENTICATED_KEY;
        }
        return next;
      }),
    );
  }

  async function saveAcl() {
    if (!aclCharacter || aclDrafts.length === 0) {
      return;
    }
    try {
      const payload = aclDrafts.map((entry) => ({
        grantee_type: entry.grantee_type,
        grantee_id: entry.grantee_type === "AUTHENTICATED_ALL" ? AUTHENTICATED_KEY : entry.grantee_id,
        perm_level: entry.perm_level,
      }));
      const nextEntries = await appendCharacterAclEntries(aclCharacter.id, payload);
      setExistingAclEntries(nextEntries);
      setAclDrafts([]);
      toast.success(t("characters.aclAppended"));
      await fetchData();
    } catch (error) {
      showErrorToast(error, t("characters.aclSaveFailed"));
    }
  }

  async function loadEffectiveAcl() {
    if (!aclCharacter || !effectiveTarget) {
      return;
    }
    setEffectiveLoading(true);
    try {
      const response = await getCharacterEffectiveAcl(
        aclCharacter.id,
        effectiveMode === "user" ? { user_uid: effectiveTarget } : { group_id: effectiveTarget },
      );
      setEffectiveItems(response);
    } catch (error) {
      showErrorToast(error, t("characters.effectiveLoadFailed"));
    } finally {
      setEffectiveLoading(false);
    }
  }

  async function handleDeleteCharacter(item: CharacterRead) {
    const accepted = await confirm({
      title: t("common.delete"),
      description: t("characters.confirmDeletePrompt", { name: item.name }),
      confirmLabel: t("common.delete"),
      cancelLabel: t("common.cancel"),
      variant: "destructive",
    });
    if (!accepted) {
      return;
    }
    try {
      await deleteCharacter(item.id);
      toast.success(t("characters.deleted"));
      await fetchData();
    } catch (error) {
      showErrorToast(error, t("characters.deleteFailed"));
    }
  }

  async function handleDeleteAclEntry(entry: CharacterAclEntryRead) {
    if (!aclCharacter) {
      return;
    }
    try {
      await deleteCharacterAclEntry(aclCharacter.id, entry.grantee_type, entry.grantee_id);
      setExistingAclEntries((prev) => prev.filter((item) => item.id !== entry.id));
      toast.success(t("characters.aclEntryDeleted"));
    } catch (error) {
      showErrorToast(error, t("characters.aclEntryDeleteFailed"));
    }
  }

  const canOperate = (item: CharacterRead) => manageableIds.has(item.id);

  if (!userInfo) {
    return <AccessCard description={t("characters.loginRequired")} />;
  }

  return (
    <PageFrame
      title={t("characters.title")}
      description={t("characters.description")}
      actions={
        <div className="flex flex-wrap gap-2">
          <Select
            value={tab}
            onValueChange={(value) => {
              setTab(value as CharacterTab);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="visible">{t("characters.tabVisible")}</SelectItem>
              {canShowManagementTab ? (
                <SelectItem value="manage">{t("characters.tabManage")}</SelectItem>
              ) : null}
            </SelectContent>
          </Select>
          {tab === "visible" ? (
            <Select
              value={visibleScope}
              onValueChange={(value) => {
                setVisibleScope(value as VisibleScopeMode);
                setPage(1);
              }}
            >
              <SelectTrigger className="w-52">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="basic_visible">{t("characters.scopeBasicVisible")}</SelectItem>
                <SelectItem value="inherited_visible">{t("characters.scopeInheritedVisible")}</SelectItem>
              </SelectContent>
            </Select>
          ) : null}
          {tab === "manage" ? (
            <Input
              className="w-56"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("characters.manageFilterPlaceholder")}
            />
          ) : null}
          <Button onClick={openCreateDialog}>
            <Plus className="mr-2 size-4" />
            {t("characters.newCharacter")}
          </Button>
        </div>
      }
    >
      <div className="mb-4 flex items-center justify-between text-sm text-muted-foreground">
        <span>{visibleCountText}</span>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>
            {t("common.previousPage")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((value) => value + 1)}
          >
            {t("common.nextPage")}
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Card key={index} className="h-56 animate-pulse bg-muted/40" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filteredItems.map((item) => (
            <Card key={item.id} className="border-border/70 bg-card/90">
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <UserRound className="size-4 text-primary" />
                      {item.name}
                    </CardTitle>
                    <CardDescription className="mt-2 max-h-24 overflow-y-auto whitespace-pre-wrap pr-2 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-border/80">
                      {item.description || t("characters.noDescription")}
                    </CardDescription>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <Badge variant="outline">#{item.id}</Badge>
                    <Badge variant={item.visibility === "public" ? "default" : "secondary"}>
                      {item.visibility === "public" ? t("characters.public") : t("characters.private")}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="max-h-36 overflow-y-auto whitespace-pre-wrap pr-2 text-sm text-muted-foreground scrollbar-thin scrollbar-track-transparent scrollbar-thumb-border/80">
                  {item.personality_prompt}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">
                    {t("characters.ownerUid")}: {item.owner_uid || "-"}
                  </Badge>
                  {canOperate(item) ? (
                    <Badge>{t("characters.manageable")}</Badge>
                  ) : (
                    <Badge variant="outline">{t("characters.readOnly")}</Badge>
                  )}
                </div>
              </CardContent>
              <CardFooter className="justify-end gap-2">
                {canOperate(item) ? (
                  <>
                    <Button variant="outline" size="sm" onClick={() => void openAclDialog(item)}>
                      <ShieldCheck className="mr-2 size-4" />
                      {t("characters.accessControl")}
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => openEditDialog(item)}>
                      <Pencil className="mr-2 size-4" />
                      {t("common.edit")}
                    </Button>
                    <Button variant="destructive" size="sm" onClick={() => void handleDeleteCharacter(item)}>
                      <Trash2 className="mr-2 size-4" />
                      {t("common.delete")}
                    </Button>
                  </>
                ) : null}
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? t("characters.dialogEditTitle") : t("characters.dialogCreateTitle")}</DialogTitle>
            <DialogDescription>{t("characters.dialogDescription")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label htmlFor="character-name">{t("common.name")}</Label>
              <Input
                id="character-name"
                value={form.name}
                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="character-description">{t("common.description")}</Label>
              <Textarea
                id="character-description"
                rows={4}
                className="max-h-40"
                value={form.description || ""}
                onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="character-prompt">{t("characters.personalityPrompt")}</Label>
              <Textarea
                id="character-prompt"
                rows={8}
                className="max-h-72"
                value={form.personality_prompt}
                onChange={(event) => setForm((prev) => ({ ...prev, personality_prompt: event.target.value }))}
              />
            </div>
            {canManageSystem ? (
              <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
                <Checkbox
                  checked={form.visibility === "public"}
                  onCheckedChange={(checked) =>
                    setForm((prev) => ({ ...prev, visibility: checked ? "public" : "private" }))
                  }
                />
                <span>{t("characters.makePublic")}</span>
              </label>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button disabled={isSaving || !form.name.trim() || !form.personality_prompt.trim()} onClick={saveCharacter}>
              {isSaving ? t("common.saving") : editing ? t("common.saveChanges") : t("characters.newCharacter")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {confirmDialog}

      <Dialog open={aclOpen} onOpenChange={setAclOpen}>
        <DialogContent className="sm:max-w-5xl">
          <DialogHeader>
            <DialogTitle>{t("characters.aclDialogTitle", { name: aclCharacter?.name || "-" })}</DialogTitle>
            <DialogDescription>
              {t("characters.aclDialogDescription")}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-6 py-2 xl:grid-cols-[1.15fr_0.85fr]">
            <div className="space-y-4">
              <Card className="border-border/70 bg-background/30">
                <CardHeader>
                  <CardTitle className="text-base">{t("characters.aclExistingTitle")}</CardTitle>
                  <CardDescription>{t("characters.aclExistingDescription")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {existingAclEntries.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
                      {t("characters.aclEmpty")}
                    </div>
                  ) : (
                    existingAclEntries.map((entry) => (
                      <div key={entry.id} className="rounded-2xl border border-border/70 p-4 text-sm">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="outline">{subjectTypeLabel(entry.grantee_type, t)}</Badge>
                          <Badge>{permissionLabel(entry.perm_level, t)}</Badge>
                        </div>
                        <div className="mt-2 break-all text-muted-foreground">{formatAclTarget(entry)}</div>
                        <div className="mt-3 flex justify-end">
                          <Button variant="ghost" size="sm" onClick={() => void handleDeleteAclEntry(entry)}>
                            <Trash2 className="mr-2 size-4" />
                            {t("common.delete")}
                          </Button>
                        </div>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>

              <Card className="border-border/70 bg-background/30">
                <CardHeader>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <CardTitle className="text-base">{t("characters.aclAppendTitle")}</CardTitle>
                      <CardDescription>{t("characters.aclAppendDescription")}</CardDescription>
                    </div>
                    <Button variant="outline" size="sm" onClick={addAclDraft}>
                      <Plus className="mr-2 size-4" />
                      {t("characters.addAclEntry")}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {aclDrafts.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
                      {t("characters.aclDraftEmpty")}
                    </div>
                  ) : (
                    aclDrafts.map((entry) => (
                      <div key={entry.localId} className="rounded-2xl border border-border/70 p-4">
                        <div className="grid gap-3 md:grid-cols-3">
                          <div className="grid gap-2">
                            <Label>{t("characters.granteeType")}</Label>
                            <Select
                              value={entry.grantee_type}
                              onValueChange={(value) =>
                                updateAclDraft(entry.localId, {
                                  grantee_type: value as AclDraftEntry["grantee_type"],
                                  grantee_id: value === "AUTHENTICATED_ALL" ? AUTHENTICATED_KEY : "",
                                })
                              }
                            >
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="USER">{t("characters.granteeUser")}</SelectItem>
                                <SelectItem value="GROUP">{t("characters.granteeGroup")}</SelectItem>
                                <SelectItem value="SUBTREE">{t("characters.granteeSubtree")}</SelectItem>
                                <SelectItem value="AUTHENTICATED_ALL">{t("characters.granteeAll")}</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="grid gap-2">
                            <Label>{t("characters.granteeTarget")}</Label>
                            {entry.grantee_type === "USER" || entry.grantee_type === "SUBTREE" ? (
                              <PopupSelect
                                title={t("characters.selectUser")}
                                description={t("characters.aclDialogDescription")}
                                placeholder={t("characters.selectUser")}
                                searchPlaceholder={t("common.search")}
                                emptyText={t("characters.aclEmpty")}
                                value={entry.grantee_id}
                                onValueChange={(value) => updateAclDraft(entry.localId, { grantee_id: value })}
                                options={aclUserOptions}
                              />
                            ) : entry.grantee_type === "GROUP" ? (
                              <PopupSelect
                                title={t("characters.selectGroup")}
                                description={t("characters.aclDialogDescription")}
                                placeholder={t("characters.selectGroup")}
                                searchPlaceholder={t("common.search")}
                                emptyText={t("characters.aclEmpty")}
                                value={entry.grantee_id}
                                onValueChange={(value) => updateAclDraft(entry.localId, { grantee_id: value })}
                                options={aclGroupOptions}
                              />
                            ) : (
                              <Input disabled value={t("characters.authenticatedAll")} />
                            )}
                          </div>
                          <div className="grid gap-2">
                            <Label>{t("characters.permissionLevel")}</Label>
                            <Select
                              value={entry.perm_level}
                              onValueChange={(value) =>
                                updateAclDraft(entry.localId, { perm_level: value as AclDraftEntry["perm_level"] })
                              }
                            >
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="READ">{t("characters.permissionRead")}</SelectItem>
                                <SelectItem value="USE">{t("characters.permissionUse")}</SelectItem>
                                <SelectItem value="MANAGE">{t("characters.permissionManage")}</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                        <div className="mt-3 flex justify-end">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setAclDrafts((prev) => prev.filter((item) => item.localId !== entry.localId))}
                          >
                            <Trash2 className="mr-2 size-4" />
                            {t("characters.removeDraft")}
                          </Button>
                        </div>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            </div>

            <div className="space-y-4">
              <Card className="border-border/70 bg-background/30">
                <CardHeader>
                  <CardTitle className="text-base">{t("characters.effectiveTitle")}</CardTitle>
                  <CardDescription>{t("characters.effectiveDescription")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid gap-2">
                    <Label>{t("characters.inspectMode")}</Label>
                    <Select
                      value={effectiveMode}
                      onValueChange={(value) => {
                        setEffectiveMode(value as EffectiveQueryMode);
                        setEffectiveTarget("");
                        setEffectiveItems([]);
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="user">{t("characters.inspectUser")}</SelectItem>
                        <SelectItem value="group">{t("characters.inspectGroup")}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-2">
                    <Label>{t("characters.inspectTarget")}</Label>
                    {effectiveMode === "user" ? (
                      <PopupSelect
                        title={t("characters.selectUser")}
                        description={t("characters.effectiveDescription")}
                        placeholder={t("characters.selectUser")}
                        searchPlaceholder={t("common.search")}
                        emptyText={t("characters.effectiveEmpty")}
                        value={effectiveTarget}
                        onValueChange={setEffectiveTarget}
                        options={aclUserOptions}
                      />
                    ) : (
                      <PopupSelect
                        title={t("characters.selectGroup")}
                        description={t("characters.effectiveDescription")}
                        placeholder={t("characters.selectGroup")}
                        searchPlaceholder={t("common.search")}
                        emptyText={t("characters.effectiveEmpty")}
                        value={effectiveTarget}
                        onValueChange={setEffectiveTarget}
                        options={aclGroupOptions}
                      />
                    )}
                  </div>
                  <Button variant="outline" onClick={() => void loadEffectiveAcl()} disabled={!effectiveTarget || effectiveLoading}>
                    {t("characters.loadEffective")}
                  </Button>
                  {effectiveItems.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
                      {effectiveLoading ? t("common.loading") : t("characters.effectiveEmpty")}
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {effectiveItems.map((item, index) => (
                        <div key={`${item.source}-${item.grantee_id}-${index}`} className="rounded-xl border border-border/70 p-3 text-sm">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="outline">{item.source}</Badge>
                            <Badge>{permissionLabel(item.perm_level, t)}</Badge>
                          </div>
                          <div className="mt-2 break-all text-muted-foreground">{formatAclTarget(item)}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="border-border/70 bg-background/30">
                <CardHeader>
                  <CardTitle className="text-base">{t("characters.permissionLegend")}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm text-muted-foreground">
                  <div className="rounded-xl border border-dashed border-border p-3">
                    <div className="mb-2 flex items-center gap-2">
                      <LockKeyhole className="size-4 text-primary" />
                      {t("characters.permissionRead")}
                    </div>
                    <div>{t("characters.permissionReadDesc")}</div>
                  </div>
                  <div className="rounded-xl border border-dashed border-border p-3">
                    <div className="mb-2 flex items-center gap-2">
                      <UserRound className="size-4 text-primary" />
                      {t("characters.permissionUse")}
                    </div>
                    <div>{t("characters.permissionUseDesc")}</div>
                  </div>
                  <div className="rounded-xl border border-dashed border-border p-3">
                    <div className="mb-2 flex items-center gap-2">
                      <Globe2 className="size-4 text-primary" />
                      {t("characters.permissionManage")}
                    </div>
                    <div>{t("characters.permissionManageDesc")}</div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAclOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={() => void saveAcl()} disabled={aclDrafts.length === 0}>
              {t("characters.appendAclEntries")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageFrame>
  );
}
