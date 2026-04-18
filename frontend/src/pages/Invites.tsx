import { useEffect, useMemo, useState } from "react";
import { isAxiosError } from "axios";
import { KeyRound, Plus, Sparkles, Ticket, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { getUserInviteSummary, listAdminUsers } from "@/api/admin-users";
import { listGroups, getGroupInviteSummary } from "@/api/groups";
import { createInviteCode, createInviteGrant, deleteInviteCode, listInviteCodes, listInviteGrants } from "@/api/invites";
import type {
  AdminUserRead,
  GroupRead,
  InviteCodeCreatePayload,
  InviteCodeRead,
  InviteQuotaGrantCreatePayload,
  InviteQuotaGrantRead,
  InviteSummary,
} from "@/api/types";
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
import { useUserStore } from "@/store/useUserStore";

const NO_GROUP = "__none";

type InviteCodeForm = {
  created_for_uid: string;
  source_type: "USER" | "GROUP" | "ADMIN_OVERRIDE";
  source_id: string;
  permanent: boolean;
  expires_at: string;
  prefix: string;
};

type InviteGrantForm = {
  target_type: "USER" | "GROUP";
  target_id: string;
  amount: string;
  is_unlimited: boolean;
  note: string;
};

function formatTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "-";
}

function codeStatus(invite: InviteCodeRead) {
  if (invite.revoked_at) return "revoked";
  if (invite.consumed_at) return "used";
  if (invite.expires_at && new Date(invite.expires_at).getTime() < Date.now()) return "expired";
  return "active";
}

export default function InvitesPage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const [users, setUsers] = useState<AdminUserRead[]>([]);
  const [groups, setGroups] = useState<GroupRead[]>([]);
  const [codes, setCodes] = useState<InviteCodeRead[]>([]);
  const [grants, setGrants] = useState<InviteQuotaGrantRead[]>([]);
  const [userSummary, setUserSummary] = useState<InviteSummary | null>(null);
  const [groupSummary, setGroupSummary] = useState<InviteSummary | null>(null);
  const [selectedGroupId, setSelectedGroupId] = useState(NO_GROUP);
  const [codeDialogOpen, setCodeDialogOpen] = useState(false);
  const [grantDialogOpen, setGrantDialogOpen] = useState(false);
  const [isSavingCode, setIsSavingCode] = useState(false);
  const [isSavingGrant, setIsSavingGrant] = useState(false);
  const [codeForm, setCodeForm] = useState<InviteCodeForm>({
    created_for_uid: "",
    source_type: "USER",
    source_id: "",
    permanent: true,
    expires_at: "",
    prefix: "",
  });
  const [grantForm, setGrantForm] = useState<InviteGrantForm>({
    target_type: "USER",
    target_id: "",
    amount: "1",
    is_unlimited: false,
    note: "",
  });

  const isAdmin = Boolean(userInfo?.can_manage_system);
  const manageableGroups = useMemo(
    () => groups.filter((group) => isAdmin || group.owner_uid === userInfo?.uid),
    [groups, isAdmin, userInfo?.uid],
  );

  useEffect(() => {
    void bootstrap();
  }, []);

  useEffect(() => {
    if (selectedGroupId === NO_GROUP) {
      setGroupSummary(null);
      return;
    }
    void loadGroupSummary(selectedGroupId);
  }, [selectedGroupId]);

  async function bootstrap() {
    if (!userInfo) {
      return;
    }
    try {
      const [usersResponse, groupsResponse, codesResponse, grantsResponse, summaryResponse] = await Promise.all([
        listAdminUsers(1, 100),
        listGroups(1, 100),
        listInviteCodes(1, 100),
        listInviteGrants(1, 100),
        getUserInviteSummary(userInfo.uid),
      ]);
      setUsers(usersResponse.items);
      setGroups(groupsResponse.items);
      setCodes(codesResponse.items);
      setGrants(grantsResponse.items);
      setUserSummary(summaryResponse);
      setCodeForm((prev) => ({
        ...prev,
        created_for_uid: userInfo.uid,
        source_id: prev.source_type === "USER" ? userInfo.uid : prev.source_id,
      }));
      setGrantForm((prev) => ({
        ...prev,
        target_id: usersResponse.items[0]?.uid || "",
      }));
    } catch (error) {
      if (isAxiosError(error)) toast.error(String(error.response?.data?.detail || error.message));
      else toast.error(t("invites.loadFailed"));
    }
  }

  async function loadGroupSummary(gid: string) {
    try {
      const summary = await getGroupInviteSummary(gid);
      setGroupSummary(summary);
    } catch (error) {
      if (isAxiosError(error)) toast.error(String(error.response?.data?.detail || error.message));
      else toast.error(t("invites.groupSummaryFailed"));
    }
  }

  async function handleCreateCode() {
    setIsSavingCode(true);
    try {
      const payload: InviteCodeCreatePayload = {
        created_for_uid: codeForm.created_for_uid || undefined,
        source_type: codeForm.source_type,
        source_id:
          codeForm.source_type === "GROUP"
            ? codeForm.source_id || undefined
            : codeForm.source_type === "USER"
              ? codeForm.source_id || userInfo?.uid || undefined
              : undefined,
        permanent: codeForm.permanent,
        expires_at: codeForm.permanent || !codeForm.expires_at ? undefined : new Date(codeForm.expires_at).toISOString(),
        prefix: codeForm.prefix.trim() || undefined,
      };
      await createInviteCode(payload);
      toast.success(t("invites.codeCreated"));
      setCodeDialogOpen(false);
      await bootstrap();
    } catch (error) {
      if (isAxiosError(error)) toast.error(String(error.response?.data?.detail || error.message));
      else toast.error(t("invites.codeCreateFailed"));
    } finally {
      setIsSavingCode(false);
    }
  }

  async function handleDeleteCode(code: string) {
    try {
      await deleteInviteCode(code);
      toast.success(t("invites.codeDeleted"));
      await bootstrap();
    } catch (error) {
      if (isAxiosError(error)) toast.error(String(error.response?.data?.detail || error.message));
      else toast.error(t("invites.codeDeleteFailed"));
    }
  }

  async function handleCreateGrant() {
    setIsSavingGrant(true);
    try {
      const payload: InviteQuotaGrantCreatePayload = {
        target_type: grantForm.target_type,
        target_id: grantForm.target_id,
        amount: Number(grantForm.amount || "0"),
        is_unlimited: grantForm.is_unlimited,
        note: grantForm.note.trim() || null,
      };
      await createInviteGrant(payload);
      toast.success(t("invites.grantCreated"));
      setGrantDialogOpen(false);
      await bootstrap();
    } catch (error) {
      if (isAxiosError(error)) toast.error(String(error.response?.data?.detail || error.message));
      else toast.error(t("invites.grantCreateFailed"));
    } finally {
      setIsSavingGrant(false);
    }
  }

  const grantTargets = grantForm.target_type === "USER" ? users : manageableGroups;

  return (
    <PageFrame
      title={t("invites.title")}
      description={t("invites.description")}
      actions={
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setGrantDialogOpen(true)}>
            <Sparkles className="mr-2 size-4" />
            {t("invites.newGrant")}
          </Button>
          <Button onClick={() => setCodeDialogOpen(true)}>
            <Plus className="mr-2 size-4" />
            {t("invites.newCode")}
          </Button>
        </div>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.25fr]">
        <div className="space-y-4">
          <Card className="border-border/70 bg-card/90">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <KeyRound className="size-4 text-primary" />
                {t("invites.summaryTitle")}
              </CardTitle>
              <CardDescription>{t("invites.summaryDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-2xl border border-border/70 p-4 text-sm">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("invites.personalQuota")}</div>
                <div className="mt-2 text-lg font-semibold">
                  {userSummary?.invite_quota_unlimited ? t("invites.unlimited") : userSummary?.invite_quota_remaining ?? 0}
                </div>
                <div className="mt-1 text-muted-foreground">{userInfo?.uid}</div>
              </div>
              <div className="grid gap-2">
                <Label>{t("invites.groupSummary")}</Label>
                <Select value={selectedGroupId} onValueChange={setSelectedGroupId}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_GROUP}>{t("invites.noGroupSelected")}</SelectItem>
                    {manageableGroups.map((group) => (
                      <SelectItem key={group.gid} value={group.gid}>
                        {group.name} · {group.gid}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="rounded-2xl border border-border/70 p-4 text-sm">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("invites.groupQuota")}</div>
                <div className="mt-2 text-lg font-semibold">
                  {groupSummary?.invite_quota_unlimited ? t("invites.unlimited") : groupSummary?.invite_quota_remaining ?? "-"}
                </div>
                <div className="mt-1 text-muted-foreground">{groupSummary?.target_id || t("invites.noGroupSelected")}</div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/70 bg-card/90">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Users className="size-4 text-primary" />
                {t("invites.grantsTitle")}
              </CardTitle>
              <CardDescription>{t("invites.grantsDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {grants.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("invites.noGrants")}</div>
              ) : (
                grants.map((grant) => (
                  <div key={grant.id} className="rounded-2xl border border-border/70 p-4 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">#{grant.id}</Badge>
                      <Badge>{grant.target_type}</Badge>
                      <Badge variant="secondary">{grant.target_id}</Badge>
                    </div>
                    <div className="mt-3 text-foreground/90">
                      {grant.is_unlimited ? t("invites.unlimitedGrant") : t("invites.finiteGrant", { amount: grant.amount })}
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      {grant.granter_uid} · {formatTime(grant.created_at)}
                    </div>
                    {grant.note ? <div className="mt-2 text-sm text-muted-foreground">{grant.note}</div> : null}
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        <Card className="border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Ticket className="size-4 text-primary" />
              {t("invites.codesTitle")}
            </CardTitle>
            <CardDescription>{t("invites.codesDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {codes.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("invites.noCodes")}</div>
            ) : (
              codes.map((invite) => {
                const status = codeStatus(invite);
                return (
                  <div key={invite.code} className="rounded-2xl border border-border/70 p-4 text-sm">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="font-medium break-all">{invite.code}</div>
                        <div className="mt-1 text-xs text-muted-foreground">{invite.created_by_uid} {"->"} {invite.parent_uid}</div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="outline">{invite.source_type}</Badge>
                        <Badge variant={status === "active" ? "default" : status === "used" ? "secondary" : "destructive"}>
                          {t(`invites.status.${status}`)}
                        </Badge>
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 text-xs text-muted-foreground md:grid-cols-2">
                      <div>{t("invites.sourceId")}: {invite.source_id || "-"}</div>
                      <div>{t("invites.expiresAt")}: {formatTime(invite.expires_at)}</div>
                      <div>{t("invites.consumedAt")}: {formatTime(invite.consumed_at)}</div>
                      <div>{t("common.createdAt")}: {formatTime(invite.created_at)}</div>
                    </div>
                    {!invite.consumed_at && !invite.revoked_at ? (
                      <div className="mt-3 flex justify-end">
                        <Button variant="ghost" size="sm" onClick={() => void handleDeleteCode(invite.code)}>
                          {t("common.delete")}
                        </Button>
                      </div>
                    ) : null}
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={codeDialogOpen} onOpenChange={setCodeDialogOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{t("invites.newCode")}</DialogTitle>
            <DialogDescription>{t("invites.codeDialogDescription")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>{t("invites.createdFor")}</Label>
              <Select value={codeForm.created_for_uid} onValueChange={(value) => setCodeForm((prev) => ({ ...prev, created_for_uid: value }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {users.map((item) => (
                    <SelectItem key={item.uid} value={item.uid}>
                      {item.username} · {item.uid}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t("invites.sourceType")}</Label>
                <Select
                  value={codeForm.source_type}
                  onValueChange={(value) =>
                    setCodeForm((prev) => ({
                      ...prev,
                      source_type: value as InviteCodeForm["source_type"],
                      source_id: value === "USER" ? userInfo?.uid || "" : "",
                    }))
                  }
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="USER">USER</SelectItem>
                    <SelectItem value="GROUP">GROUP</SelectItem>
                    {isAdmin ? <SelectItem value="ADMIN_OVERRIDE">ADMIN_OVERRIDE</SelectItem> : null}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>{t("invites.sourceId")}</Label>
                {codeForm.source_type === "GROUP" ? (
                  <Select value={codeForm.source_id} onValueChange={(value) => setCodeForm((prev) => ({ ...prev, source_id: value }))}>
                    <SelectTrigger><SelectValue placeholder={t("invites.selectGroup")} /></SelectTrigger>
                    <SelectContent>
                      {manageableGroups.map((group) => (
                        <SelectItem key={group.gid} value={group.gid}>
                          {group.name} · {group.gid}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    value={codeForm.source_type === "USER" ? codeForm.source_id || userInfo?.uid || "" : t("invites.adminOverride")}
                    disabled
                  />
                )}
              </div>
            </div>
            <div className="grid gap-2">
              <Label>{t("invites.prefix")}</Label>
              <Input value={codeForm.prefix} onChange={(event) => setCodeForm((prev) => ({ ...prev, prefix: event.target.value }))} />
            </div>
            <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
              <Checkbox checked={codeForm.permanent} onCheckedChange={(checked) => setCodeForm((prev) => ({ ...prev, permanent: Boolean(checked) }))} />
              <span>{t("invites.permanent")}</span>
            </label>
            {!codeForm.permanent ? (
              <div className="grid gap-2">
                <Label>{t("invites.expiresAt")}</Label>
                <Input type="datetime-local" value={codeForm.expires_at} onChange={(event) => setCodeForm((prev) => ({ ...prev, expires_at: event.target.value }))} />
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCodeDialogOpen(false)}>{t("common.cancel")}</Button>
            <Button disabled={isSavingCode || !codeForm.created_for_uid || (codeForm.source_type === "GROUP" && !codeForm.source_id)} onClick={() => void handleCreateCode()}>
              {isSavingCode ? t("common.saving") : t("common.create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={grantDialogOpen} onOpenChange={setGrantDialogOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{t("invites.newGrant")}</DialogTitle>
            <DialogDescription>{t("invites.grantDialogDescription")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t("invites.targetType")}</Label>
                <Select value={grantForm.target_type} onValueChange={(value) => setGrantForm((prev) => ({ ...prev, target_type: value as InviteGrantForm["target_type"], target_id: "" }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="USER">USER</SelectItem>
                    <SelectItem value="GROUP">GROUP</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>{t("invites.targetId")}</Label>
                <Select value={grantForm.target_id} onValueChange={(value) => setGrantForm((prev) => ({ ...prev, target_id: value }))}>
                  <SelectTrigger><SelectValue placeholder={grantForm.target_type === "USER" ? t("invites.selectUser") : t("invites.selectGroup")} /></SelectTrigger>
                  <SelectContent>
                    {grantTargets.map((item) => (
                      <SelectItem key={grantForm.target_type === "USER" ? (item as AdminUserRead).uid : (item as GroupRead).gid} value={grantForm.target_type === "USER" ? (item as AdminUserRead).uid : (item as GroupRead).gid}>
                        {grantForm.target_type === "USER"
                          ? `${(item as AdminUserRead).username} · ${(item as AdminUserRead).uid}`
                          : `${(item as GroupRead).name} · ${(item as GroupRead).gid}`}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t("invites.amount")}</Label>
                <Input type="number" min="0" disabled={grantForm.is_unlimited} value={grantForm.amount} onChange={(event) => setGrantForm((prev) => ({ ...prev, amount: event.target.value }))} />
              </div>
              <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
                <Checkbox checked={grantForm.is_unlimited} onCheckedChange={(checked) => setGrantForm((prev) => ({ ...prev, is_unlimited: Boolean(checked) }))} />
                <span>{t("invites.unlimitedGrant")}</span>
              </label>
            </div>
            <div className="grid gap-2">
              <Label>{t("invites.note")}</Label>
              <Textarea rows={4} value={grantForm.note} onChange={(event) => setGrantForm((prev) => ({ ...prev, note: event.target.value }))} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setGrantDialogOpen(false)}>{t("common.cancel")}</Button>
            <Button disabled={isSavingGrant || !grantForm.target_id} onClick={() => void handleCreateGrant()}>
              {isSavingGrant ? t("common.saving") : t("common.create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageFrame>
  );
}
