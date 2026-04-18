import { useEffect, useMemo, useState } from "react";
import { isAxiosError } from "axios";
import { Globe2, LockKeyhole, Pencil, Plus, ShieldCheck, Trash2, UserRound } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { listAdminUsers } from "@/api/admin-users";
import {
  createCharacter,
  deleteCharacter,
  getCharacterAcl,
  getCharacterEffectiveAcl,
  getCharacters,
  replaceCharacterAcl,
  updateCharacter,
} from "@/api/characters";
import { listGroups } from "@/api/groups";
import type {
  AdminUserRead,
  CharacterAclEffectiveEntry,
  CharacterAclEntryRead,
  CharacterAclEntryWrite,
  CharacterPayload,
  CharacterRead,
  GroupRead,
} from "@/api/types";
import AccessCard from "@/components/AccessCard";
import PageFrame from "@/components/PageFrame";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
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

type ScopeMode = "mine" | "all";
type EffectiveQueryMode = "user" | "group";
type AclDraftEntry = CharacterAclEntryWrite & { localId: string };

function permissionLabel(level: string | number, t: (key: string) => string) {
  if (typeof level === "number") {
    return level === 3 ? t("characters.permissionManage") : level === 2 ? t("characters.permissionUse") : t("characters.permissionRead");
  }
  if (level === "MANAGE") return t("characters.permissionManage");
  if (level === "USE") return t("characters.permissionUse");
  return t("characters.permissionRead");
}

function toDraftEntry(entry: CharacterAclEntryRead): AclDraftEntry {
  return {
    localId: String(entry.id),
    grantee_type: entry.grantee_type as AclDraftEntry["grantee_type"],
    grantee_id: entry.grantee_id,
    perm_level: entry.perm_level >= 3 ? "MANAGE" : entry.perm_level >= 2 ? "USE" : "READ",
  };
}

export default function CharactersPage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const [items, setItems] = useState<CharacterRead[]>([]);
  const [manageableIds, setManageableIds] = useState<Set<number>>(new Set());
  const [page, setPage] = useState(1);
  const [pageSize] = useState(12);
  const [totalPages, setTotalPages] = useState(1);
  const [scope, setScope] = useState<ScopeMode>("mine");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<CharacterRead | null>(null);
  const [deleting, setDeleting] = useState<CharacterRead | null>(null);
  const [form, setForm] = useState<CharacterPayload>(EMPTY_FORM);

  const [aclOpen, setAclOpen] = useState(false);
  const [aclCharacter, setAclCharacter] = useState<CharacterRead | null>(null);
  const [aclEntries, setAclEntries] = useState<AclDraftEntry[]>([]);
  const [aclUsers, setAclUsers] = useState<AdminUserRead[]>([]);
  const [aclGroups, setAclGroups] = useState<GroupRead[]>([]);
  const [effectiveMode, setEffectiveMode] = useState<EffectiveQueryMode>("user");
  const [effectiveTarget, setEffectiveTarget] = useState("");
  const [effectiveItems, setEffectiveItems] = useState<CharacterAclEffectiveEntry[]>([]);
  const [effectiveLoading, setEffectiveLoading] = useState(false);

  const canManageSystem = Boolean(userInfo?.can_manage_system);

  async function fetchData() {
    setIsLoading(true);
    try {
      const [response, manageableResponse] = await Promise.all([
        getCharacters(page, pageSize, scope),
        getCharacters(1, 100, "mine"),
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
  }, [page, scope]);

  const visibleCountText = useMemo(() => {
    if (items.length === 0) {
      return t("characters.emptyStats");
    }
    return t("characters.pageStats", { page, totalPages, count: items.length });
  }, [items.length, page, t, totalPages]);

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
      if (isAxiosError(error)) {
        toast.error(String(error.response?.data?.detail || error.message));
      } else {
        toast.error(t("characters.saveFailed"));
      }
    } finally {
      setIsSaving(false);
    }
  }

  async function confirmDelete() {
    if (!deleting) {
      return;
    }

    try {
      await deleteCharacter(deleting.id);
      toast.success(t("characters.deleted"));
      setDeleting(null);
      await fetchData();
    } catch (error) {
      if (isAxiosError(error)) {
        toast.error(String(error.response?.data?.detail || error.message));
      } else {
        toast.error(t("characters.deleteFailed"));
      }
    }
  }

  async function openAclDialog(item: CharacterRead) {
    setAclOpen(true);
    setAclCharacter(item);
    setAclEntries([]);
    setEffectiveItems([]);
    setEffectiveTarget(userInfo?.uid || "");
    setEffectiveMode("user");
    try {
      const [aclResponse, usersResponse, groupsResponse] = await Promise.all([
        getCharacterAcl(item.id),
        listAdminUsers(1, 100),
        listGroups(1, 100),
      ]);
      setAclEntries(aclResponse.map(toDraftEntry));
      setAclUsers(usersResponse.items);
      setAclGroups(groupsResponse.items.filter((group) => canManageSystem || group.owner_uid === userInfo?.uid));
    } catch (error) {
      setAclOpen(false);
      if (isAxiosError(error)) {
        toast.error(String(error.response?.data?.detail || error.message));
      } else {
        toast.error(t("characters.aclLoadFailed"));
      }
    }
  }

  function addAclEntry() {
    setAclEntries((prev) => [
      ...prev,
      {
        localId: `${Date.now()}-${prev.length}`,
        grantee_type: "USER",
        grantee_id: userInfo?.uid || "",
        perm_level: "READ",
      },
    ]);
  }

  function updateAclEntry(localId: string, patch: Partial<AclDraftEntry>) {
    setAclEntries((prev) =>
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
    if (!aclCharacter) {
      return;
    }
    try {
      const payload = aclEntries.map((entry) => ({
        grantee_type: entry.grantee_type,
        grantee_id: entry.grantee_type === "AUTHENTICATED_ALL" ? AUTHENTICATED_KEY : entry.grantee_id,
        perm_level: entry.perm_level,
      }));
      await replaceCharacterAcl(aclCharacter.id, payload);
      toast.success(t("characters.aclSaved"));
      setAclOpen(false);
      await fetchData();
    } catch (error) {
      if (isAxiosError(error)) {
        toast.error(String(error.response?.data?.detail || error.message));
      } else {
        toast.error(t("characters.aclSaveFailed"));
      }
    }
  }

  async function loadEffectiveAcl() {
    if (!aclCharacter || !effectiveTarget) {
      return;
    }
    setEffectiveLoading(true);
    try {
      const response = await getCharacterEffectiveAcl(aclCharacter.id, effectiveMode === "user" ? { user_uid: effectiveTarget } : { group_id: effectiveTarget });
      setEffectiveItems(response);
    } catch (error) {
      if (isAxiosError(error)) {
        toast.error(String(error.response?.data?.detail || error.message));
      } else {
        toast.error(t("characters.effectiveLoadFailed"));
      }
    } finally {
      setEffectiveLoading(false);
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
          <Select value={scope} onValueChange={(value) => { setScope(value as ScopeMode); setPage(1); }}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="mine">{t("characters.scopeMine")}</SelectItem>
              <SelectItem value="all">{t("characters.scopeAll")}</SelectItem>
            </SelectContent>
          </Select>
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
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>
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
          {items.map((item) => (
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
                  {canOperate(item) ? <Badge>{t("characters.manageable")}</Badge> : <Badge variant="outline">{t("characters.readOnly")}</Badge>}
                </div>
              </CardContent>
              <CardFooter className="justify-end gap-2">
                {canOperate(item) ? (
                  <>
                    <Button variant="outline" size="sm" onClick={() => openAclDialog(item)}>
                      <ShieldCheck className="mr-2 size-4" />
                      {t("characters.accessControl")}
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => openEditDialog(item)}>
                      <Pencil className="mr-2 size-4" />
                      {t("common.edit")}
                    </Button>
                    <Button variant="destructive" size="sm" onClick={() => setDeleting(item)}>
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
              <Input id="character-name" value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="character-description">{t("common.description")}</Label>
              <Textarea id="character-description" rows={4} className="max-h-40" value={form.description || ""} onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="character-prompt">{t("characters.personalityPrompt")}</Label>
              <Textarea id="character-prompt" rows={8} className="max-h-72" value={form.personality_prompt} onChange={(event) => setForm((prev) => ({ ...prev, personality_prompt: event.target.value }))} />
            </div>
            {canManageSystem ? (
              <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
                <Checkbox checked={form.visibility === "public"} onCheckedChange={(checked) => setForm((prev) => ({ ...prev, visibility: checked ? "public" : "private" }))} />
                <span>{t("characters.makePublic")}</span>
              </label>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>{t("common.cancel")}</Button>
            <Button disabled={isSaving || !form.name.trim() || !form.personality_prompt.trim()} onClick={saveCharacter}>
              {isSaving ? t("common.saving") : editing ? t("common.saveChanges") : t("characters.newCharacter")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={aclOpen} onOpenChange={setAclOpen}>
        <DialogContent className="sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle>{t("characters.aclDialogTitle", { name: aclCharacter?.name || "-" })}</DialogTitle>
            <DialogDescription>{t("characters.aclDialogDescription")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-6 py-2 xl:grid-cols-[1.15fr_0.85fr]">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">{t("characters.aclEntries")}</div>
                <Button variant="outline" size="sm" onClick={addAclEntry}>
                  <Plus className="mr-2 size-4" />
                  {t("characters.addAclEntry")}
                </Button>
              </div>
              <div className="space-y-3">
                {aclEntries.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">{t("characters.aclEmpty")}</div>
                ) : (
                  aclEntries.map((entry) => (
                    <div key={entry.localId} className="rounded-2xl border border-border/70 p-4">
                      <div className="grid gap-3 md:grid-cols-3">
                        <div className="grid gap-2">
                          <Label>{t("characters.granteeType")}</Label>
                          <Select value={entry.grantee_type} onValueChange={(value) => updateAclEntry(entry.localId, { grantee_type: value as AclDraftEntry["grantee_type"], grantee_id: value === "AUTHENTICATED_ALL" ? AUTHENTICATED_KEY : "" })}>
                            <SelectTrigger><SelectValue /></SelectTrigger>
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
                            <Select value={entry.grantee_id} onValueChange={(value) => updateAclEntry(entry.localId, { grantee_id: value })}>
                              <SelectTrigger><SelectValue placeholder={t("characters.selectUser")} /></SelectTrigger>
                              <SelectContent>
                                {aclUsers.map((item) => (
                                  <SelectItem key={item.uid} value={item.uid}>
                                    {item.username} · {item.uid}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          ) : entry.grantee_type === "GROUP" ? (
                            <Select value={entry.grantee_id} onValueChange={(value) => updateAclEntry(entry.localId, { grantee_id: value })}>
                              <SelectTrigger><SelectValue placeholder={t("characters.selectGroup")} /></SelectTrigger>
                              <SelectContent>
                                {aclGroups.map((group) => (
                                  <SelectItem key={group.gid} value={group.gid}>
                                    {group.name} · {group.gid}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          ) : (
                            <Input disabled value={t("characters.authenticatedAll")} />
                          )}
                        </div>
                        <div className="grid gap-2">
                          <Label>{t("characters.permissionLevel")}</Label>
                          <Select value={entry.perm_level} onValueChange={(value) => updateAclEntry(entry.localId, { perm_level: value as AclDraftEntry["perm_level"] })}>
                            <SelectTrigger><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="READ">{t("characters.permissionRead")}</SelectItem>
                              <SelectItem value="USE">{t("characters.permissionUse")}</SelectItem>
                              <SelectItem value="MANAGE">{t("characters.permissionManage")}</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <div className="mt-3 flex justify-end">
                        <Button variant="ghost" size="sm" onClick={() => setAclEntries((prev) => prev.filter((item) => item.localId !== entry.localId))}>
                          <Trash2 className="mr-2 size-4" />
                          {t("common.delete")}
                        </Button>
                      </div>
                    </div>
                  ))
                )}
              </div>
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
                    <Select value={effectiveMode} onValueChange={(value) => { setEffectiveMode(value as EffectiveQueryMode); setEffectiveTarget(""); setEffectiveItems([]); }}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="user">{t("characters.inspectUser")}</SelectItem>
                        <SelectItem value="group">{t("characters.inspectGroup")}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-2">
                    <Label>{t("characters.inspectTarget")}</Label>
                    {effectiveMode === "user" ? (
                      <Select value={effectiveTarget} onValueChange={setEffectiveTarget}>
                        <SelectTrigger><SelectValue placeholder={t("characters.selectUser")} /></SelectTrigger>
                        <SelectContent>
                          {aclUsers.map((item) => (
                            <SelectItem key={item.uid} value={item.uid}>
                              {item.username} · {item.uid}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : (
                      <Select value={effectiveTarget} onValueChange={setEffectiveTarget}>
                        <SelectTrigger><SelectValue placeholder={t("characters.selectGroup")} /></SelectTrigger>
                        <SelectContent>
                          {aclGroups.map((group) => (
                            <SelectItem key={group.gid} value={group.gid}>
                              {group.name} · {group.gid}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
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
                          <div className="mt-2 break-all text-muted-foreground">{item.grantee_id || t("characters.authenticatedAll")}</div>
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
                    <div className="mb-2 flex items-center gap-2"><LockKeyhole className="size-4 text-primary" />{t("characters.permissionRead")}</div>
                    <div>{t("characters.permissionReadDesc")}</div>
                  </div>
                  <div className="rounded-xl border border-dashed border-border p-3">
                    <div className="mb-2 flex items-center gap-2"><UserRound className="size-4 text-primary" />{t("characters.permissionUse")}</div>
                    <div>{t("characters.permissionUseDesc")}</div>
                  </div>
                  <div className="rounded-xl border border-dashed border-border p-3">
                    <div className="mb-2 flex items-center gap-2"><Globe2 className="size-4 text-primary" />{t("characters.permissionManage")}</div>
                    <div>{t("characters.permissionManageDesc")}</div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAclOpen(false)}>{t("common.cancel")}</Button>
            <Button onClick={() => void saveAcl()}>{t("characters.saveAcl")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => !open && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("characters.confirmDeleteTitle")}</AlertDialogTitle>
            <AlertDialogDescription>{t("characters.confirmDeleteDescription")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("common.cancel")}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete}>{t("characters.continueDelete")}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageFrame>
  );
}
