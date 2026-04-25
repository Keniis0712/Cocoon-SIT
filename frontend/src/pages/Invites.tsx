import { useEffect, useMemo, useState } from "react";
import { Gift, Plus, ShieldOff, Ticket, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { listAdminUsers } from "@/api/admin-users";
import { showErrorToast } from "@/api/client";
import { listGroups } from "@/api/groups";
import {
  createInviteCode,
  createInviteGrant,
  deleteInviteCode,
  getGroupInviteSummary,
  getMyInviteSummary,
  listInviteCodes,
  listInviteGrants,
  revokeInviteGrant,
} from "@/api/invites";
import type {
  AdminUserRead,
  GroupRead,
  InviteCodeCreatePayload,
  InviteCodeRead,
  InviteQuotaGrantCreatePayload,
  InviteQuotaGrantRead,
  InviteSummary,
} from "@/api/types/access";
import { PopupSelect } from "@/components/composes/PopupSelect";
import { useConfirmDialog } from "@/components/composes/useConfirmDialog";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useUserStore } from "@/store/useUserStore";

type InviteCodeForm = {
  created_for_uid: string;
  registration_group_id: string;
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

function renderSummaryValue(t: (key: string) => string, summary: InviteSummary | null) {
  if (!summary) return "0";
  if (summary.invite_quota_unlimited) return t("invites.unlimited");
  return String(summary.invite_quota_remaining);
}

export default function InvitesPage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const [users, setUsers] = useState<AdminUserRead[]>([]);
  const [groups, setGroups] = useState<GroupRead[]>([]);
  const [codes, setCodes] = useState<InviteCodeRead[]>([]);
  const [grants, setGrants] = useState<InviteQuotaGrantRead[]>([]);
  const [personalSummary, setPersonalSummary] = useState<InviteSummary | null>(null);
  const [groupSummary, setGroupSummary] = useState<InviteSummary | null>(null);
  const [selectedGroupId, setSelectedGroupId] = useState("");
  const [codeDialogOpen, setCodeDialogOpen] = useState(false);
  const [grantDialogOpen, setGrantDialogOpen] = useState(false);
  const [isSavingCode, setIsSavingCode] = useState(false);
  const [isSavingGrant, setIsSavingGrant] = useState(false);
  const { confirm, confirmDialog } = useConfirmDialog();
  const [codeForm, setCodeForm] = useState<InviteCodeForm>({
    created_for_uid: "",
    registration_group_id: "",
    source_type: "USER",
    source_id: "",
    permanent: false,
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
  const selectedGroup = useMemo(
    () => groups.find((group) => group.gid === selectedGroupId) ?? null,
    [groups, selectedGroupId],
  );
  const groupOptions = useMemo(
    () =>
      groups.map((group) => ({
        value: group.gid,
        label: group.name,
        description: group.group_path || group.gid,
        keywords: [group.gid],
      })),
    [groups],
  );
  const userOptions = useMemo(
    () =>
      users.map((item) => ({
        value: item.uid,
        label: item.username,
        description: item.uid,
        keywords: [item.email || ""],
      })),
    [users],
  );
  const groupNameMap = useMemo(() => new Map(groups.map((group) => [group.gid, group.name])), [groups]);

  useEffect(() => {
    void bootstrap();
  }, []);

  useEffect(() => {
    if (!selectedGroupId) {
      setGroupSummary(null);
      return;
    }
    void refreshGroupSummary(selectedGroupId);
  }, [selectedGroupId]);

  async function bootstrap() {
    if (!userInfo) return;
    try {
      const [usersResponse, groupsResponse, codesResponse, grantsResponse, personalQuota] = await Promise.all([
        listAdminUsers(1, 200),
        listGroups(1, 200),
        listInviteCodes(1, 200),
        listInviteGrants(1, 200),
        getMyInviteSummary(),
      ]);
      setUsers(usersResponse.items);
      setGroups(groupsResponse.items);
      setCodes(codesResponse.items);
      setGrants(grantsResponse.items);
      setPersonalSummary(personalQuota);
      const defaultGroupId = selectedGroupId || groupsResponse.items.find((item) => item.parent_group_id)?.gid || groupsResponse.items[0]?.gid || "";
      setSelectedGroupId(defaultGroupId);
      setCodeForm((prev) => ({
        ...prev,
        created_for_uid: prev.created_for_uid || userInfo.uid,
        registration_group_id: prev.registration_group_id || defaultGroupId,
        source_id: prev.source_type === "USER" ? prev.source_id || userInfo.uid : prev.source_id || defaultGroupId,
      }));
      setGrantForm((prev) => ({
        ...prev,
        target_id: prev.target_id || userInfo.uid,
      }));
      if (defaultGroupId) {
        await refreshGroupSummary(defaultGroupId);
      }
    } catch (error) {
      showErrorToast(error, t("invites.loadFailed"));
    }
  }

  async function refreshGroupSummary(gid: string) {
    try {
      const summary = await getGroupInviteSummary(gid);
      setGroupSummary(summary);
    } catch (error) {
      showErrorToast(error, t("invites.groupSummaryFailed"));
    }
  }

  async function handleCreateCode() {
    setIsSavingCode(true);
    try {
      const payload: InviteCodeCreatePayload = {
        created_for_uid: codeForm.created_for_uid || undefined,
        registration_group_id: codeForm.registration_group_id,
        source_type: codeForm.source_type,
        source_id:
          codeForm.source_type === "GROUP"
            ? codeForm.source_id || undefined
            : codeForm.source_type === "USER"
              ? codeForm.source_id || userInfo?.uid || undefined
              : undefined,
        permanent: isAdmin ? codeForm.permanent : false,
        expires_at:
          isAdmin && codeForm.permanent
            ? undefined
            : !codeForm.expires_at
              ? undefined
              : new Date(codeForm.expires_at).toISOString(),
        prefix: codeForm.prefix.trim() || undefined,
      };
      await createInviteCode(payload);
      toast.success(t("invites.codeCreated"));
      setCodeDialogOpen(false);
      await bootstrap();
    } catch (error) {
      showErrorToast(error, t("invites.codeCreateFailed"));
    } finally {
      setIsSavingCode(false);
    }
  }

  async function handleRevokeCode(code: string) {
    const accepted = await confirm({
      title: t("invites.revokeCode"),
      description: code,
      confirmLabel: t("common.delete"),
      cancelLabel: t("common.cancel"),
      variant: "destructive",
    });
    if (!accepted) {
      return;
    }
    try {
      await deleteInviteCode(code);
      toast.success(t("invites.codeDeleted"));
      await bootstrap();
    } catch (error) {
      showErrorToast(error, t("invites.codeDeleteFailed"));
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
        note: grantForm.note.trim() || undefined,
      };
      await createInviteGrant(payload);
      toast.success(t("invites.grantCreated"));
      setGrantDialogOpen(false);
      await bootstrap();
    } catch (error) {
      showErrorToast(error, t("invites.grantCreateFailed"));
    } finally {
      setIsSavingGrant(false);
    }
  }

  async function handleRevokeGrant(grant: InviteQuotaGrantRead) {
    const accepted = await confirm({
      title: t("invites.revokeGrant"),
      description: `${grant.target_type} / ${grant.target_id}`,
      confirmLabel: t("common.delete"),
      cancelLabel: t("common.cancel"),
      variant: "destructive",
    });
    if (!accepted) {
      return;
    }
    try {
      await revokeInviteGrant(grant.id);
      toast.success(t("invites.grantRevoked"));
      await bootstrap();
    } catch (error) {
      showErrorToast(error, t("invites.grantRevokeFailed"));
    }
  }

  return (
    <PageFrame
      title={t("invites.title")}
      description={t("invites.description")}
      actions={
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setGrantDialogOpen(true)}>
            <Gift className="mr-2 size-4" />
            {t("invites.newGrant")}
          </Button>
          <Button onClick={() => setCodeDialogOpen(true)}>
            <Plus className="mr-2 size-4" />
            {t("invites.newCode")}
          </Button>
        </div>
      }
    >
      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <Card className="border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle className="text-base">{t("invites.summaryTitle")}</CardTitle>
            <CardDescription>{t("invites.summaryDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded-2xl border border-border/70 p-4">
              <div className="text-sm text-muted-foreground">{t("invites.personalQuota")}</div>
              <div className="mt-2 text-3xl font-semibold">{renderSummaryValue(t, personalSummary)}</div>
            </div>
            <div className="rounded-2xl border border-border/70 p-4">
              <div className="text-sm text-muted-foreground">{t("invites.groupQuota")}</div>
              <div className="mt-2 text-3xl font-semibold">{selectedGroup ? renderSummaryValue(t, groupSummary) : t("invites.noGroupSelected")}</div>
              {selectedGroup ? <div className="mt-2 text-xs text-muted-foreground">{selectedGroup.group_path || selectedGroup.name}</div> : null}
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle className="text-base">{t("invites.groupSummary")}</CardTitle>
            <CardDescription>{t("invites.summaryDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label>{t("groups.title")}</Label>
              <PopupSelect
                title={t("invites.selectGroup")}
                description={t("invites.groupSummary")}
                placeholder={t("invites.selectGroup")}
                searchPlaceholder={t("common.search")}
                emptyText={t("invites.noGroupSelected")}
                value={selectedGroupId}
                onValueChange={setSelectedGroupId}
                options={groupOptions}
              />
            </div>
            <div className="rounded-2xl border border-dashed border-border/70 p-4 text-sm text-muted-foreground">
              {selectedGroup ? `${selectedGroup.name} / ${renderSummaryValue(t, groupSummary)}` : t("invites.noGroupSelected")}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <Card className="border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Gift className="size-4 text-primary" />
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
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="font-medium">
                        {grant.target_type} / {grant.target_type === "GROUP" ? groupNameMap.get(grant.target_id) || grant.target_id : grant.target_id}
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">{grant.granter_uid || "-"}</div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="outline">
                        {grant.is_unlimited ? t("invites.unlimitedGrant") : t("invites.finiteGrant", { amount: grant.amount })}
                      </Badge>
                      {grant.revoked_at ? <Badge variant="secondary">{t("invites.revokedGrant")}</Badge> : null}
                    </div>
                  </div>
                  <div className="mt-3 text-xs text-muted-foreground">
                    <div>{grant.note || "-"}</div>
                    <div className="mt-1">{formatTime(grant.created_at)}</div>
                    {grant.revoked_at ? <div className="mt-1">{t("invites.revokedAt")}: {formatTime(grant.revoked_at)}</div> : null}
                  </div>
                  {isAdmin && !grant.revoked_at ? (
                    <div className="mt-3 flex justify-end">
                      <Button variant="ghost" size="sm" onClick={() => void handleRevokeGrant(grant)}>
                        <ShieldOff className="mr-2 size-4" />
                        {t("invites.revokeGrant")}
                      </Button>
                    </div>
                  ) : null}
                </div>
              ))
            )}
          </CardContent>
        </Card>

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
                const canRevoke = status === "active";
                return (
                  <div key={invite.code} className="rounded-2xl border border-border/70 p-4 text-sm">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="break-all font-medium">{invite.code}</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {invite.created_by_uid} {"->"} {invite.parent_uid}
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">{invite.source_type}</Badge>
                        <Badge variant={status === "active" ? "default" : status === "used" ? "secondary" : "destructive"}>
                          {t(`invites.status.${status}`)}
                        </Badge>
                        {canRevoke ? (
                          <Button size="sm" variant="ghost" onClick={() => void handleRevokeCode(invite.code)}>
                            <Trash2 className="mr-2 size-4" />
                            {t("common.delete")}
                          </Button>
                        ) : null}
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 text-xs text-muted-foreground md:grid-cols-2">
                      <div>{t("invites.registrationGroup")}: {invite.registration_group_id ? groupNameMap.get(invite.registration_group_id) || invite.registration_group_id : "-"}</div>
                      <div>{t("invites.sourceId")}: {invite.source_id || "-"}</div>
                      <div>{t("invites.expiresAt")}: {formatTime(invite.expires_at)}</div>
                      <div>{t("invites.consumedAt")}: {formatTime(invite.consumed_at)}</div>
                      <div>{t("common.createdAt")}: {formatTime(invite.created_at)}</div>
                    </div>
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={codeDialogOpen} onOpenChange={setCodeDialogOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t("invites.newCode")}</DialogTitle>
            <DialogDescription>{t("invites.codeDialogDescription")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>{t("invites.createdFor")}</Label>
              <PopupSelect
                title={t("invites.createdFor")}
                description={t("invites.codeDialogDescription")}
                placeholder={t("invites.selectUser")}
                searchPlaceholder={t("common.search")}
                emptyText={t("invites.noCodes")}
                value={codeForm.created_for_uid}
                onValueChange={(value) => setCodeForm((prev) => ({ ...prev, created_for_uid: value }))}
                options={userOptions}
              />
            </div>
            <div className="grid gap-2">
              <Label>{t("invites.registrationGroup")}</Label>
              <PopupSelect
                title={t("invites.registrationGroup")}
                description={t("invites.registrationGroupDescription")}
                placeholder={t("invites.selectGroup")}
                searchPlaceholder={t("common.search")}
                emptyText={t("invites.noGroupSelected")}
                value={codeForm.registration_group_id}
                onValueChange={(value) => setCodeForm((prev) => ({ ...prev, registration_group_id: value }))}
                options={groupOptions}
              />
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
                      source_id:
                        value === "USER"
                          ? userInfo?.uid || ""
                          : value === "GROUP"
                            ? selectedGroupId
                            : "",
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
                  <PopupSelect
                    title={t("invites.selectGroup")}
                    placeholder={t("invites.selectGroup")}
                    searchPlaceholder={t("common.search")}
                    emptyText={t("invites.noGroupSelected")}
                    value={codeForm.source_id}
                    onValueChange={(value) => setCodeForm((prev) => ({ ...prev, source_id: value }))}
                    options={groupOptions}
                  />
                ) : codeForm.source_type === "USER" ? (
                  <PopupSelect
                    title={t("invites.selectUser")}
                    placeholder={t("invites.selectUser")}
                    searchPlaceholder={t("common.search")}
                    emptyText={t("invites.noCodes")}
                    value={codeForm.source_id || userInfo?.uid || ""}
                    onValueChange={(value) => setCodeForm((prev) => ({ ...prev, source_id: value }))}
                    options={userOptions}
                  />
                ) : (
                  <Input value={t("invites.adminOverride")} disabled />
                )}
              </div>
            </div>
            <div className="grid gap-2">
              <Label>{t("invites.prefix")}</Label>
              <Input value={codeForm.prefix} onChange={(event) => setCodeForm((prev) => ({ ...prev, prefix: event.target.value }))} />
            </div>
            <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
              <Checkbox
                checked={isAdmin ? codeForm.permanent : false}
                disabled={!isAdmin}
                onCheckedChange={(checked) => setCodeForm((prev) => ({ ...prev, permanent: Boolean(checked) }))}
              />
              <span>{t("invites.permanent")}</span>
            </label>
            {!isAdmin ? <div className="text-xs text-muted-foreground">{t("invites.permanentAdminOnly")}</div> : null}
            {!codeForm.permanent ? (
              <div className="grid gap-2">
                <Label>{t("invites.expiresAt")}</Label>
                <Input type="datetime-local" value={codeForm.expires_at} onChange={(event) => setCodeForm((prev) => ({ ...prev, expires_at: event.target.value }))} />
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCodeDialogOpen(false)}>{t("common.cancel")}</Button>
            <Button
              disabled={
                isSavingCode ||
                !codeForm.created_for_uid ||
                !codeForm.registration_group_id ||
                (codeForm.source_type !== "ADMIN_OVERRIDE" && !codeForm.source_id) ||
                (!codeForm.permanent && !codeForm.expires_at)
              }
              onClick={() => void handleCreateCode()}
            >
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
                <Select
                  value={grantForm.target_type}
                  onValueChange={(value) =>
                    setGrantForm((prev) => ({
                      ...prev,
                      target_type: value as InviteGrantForm["target_type"],
                      target_id: value === "USER" ? userInfo?.uid || "" : selectedGroupId,
                    }))
                  }
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="USER">USER</SelectItem>
                    <SelectItem value="GROUP">GROUP</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>{t("invites.targetId")}</Label>
                {grantForm.target_type === "USER" ? (
                  <PopupSelect
                    title={t("invites.selectUser")}
                    placeholder={t("invites.selectUser")}
                    searchPlaceholder={t("common.search")}
                    emptyText={t("invites.noCodes")}
                    value={grantForm.target_id}
                    onValueChange={(value) => setGrantForm((prev) => ({ ...prev, target_id: value }))}
                    options={userOptions}
                  />
                ) : (
                  <PopupSelect
                    title={t("invites.selectGroup")}
                    placeholder={t("invites.selectGroup")}
                    searchPlaceholder={t("common.search")}
                    emptyText={t("invites.noGroupSelected")}
                    value={grantForm.target_id}
                    onValueChange={(value) => setGrantForm((prev) => ({ ...prev, target_id: value }))}
                    options={groupOptions}
                  />
                )}
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t("invites.amount")}</Label>
                <Input
                  type="number"
                  min="1"
                  value={grantForm.amount}
                  disabled={grantForm.is_unlimited}
                  onChange={(event) => setGrantForm((prev) => ({ ...prev, amount: event.target.value }))}
                />
              </div>
              <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
                <Checkbox checked={grantForm.is_unlimited} onCheckedChange={(checked) => setGrantForm((prev) => ({ ...prev, is_unlimited: Boolean(checked) }))} />
                <span>{t("invites.unlimitedGrant")}</span>
              </label>
            </div>
            <div className="grid gap-2">
              <Label>{t("invites.note")}</Label>
              <Input value={grantForm.note} onChange={(event) => setGrantForm((prev) => ({ ...prev, note: event.target.value }))} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setGrantDialogOpen(false)}>{t("common.cancel")}</Button>
            <Button
              disabled={
                isSavingGrant ||
                !grantForm.target_id ||
                (!grantForm.is_unlimited && Number(grantForm.amount || "0") < 1)
              }
              onClick={() => void handleCreateGrant()}
            >
              {isSavingGrant ? t("common.saving") : t("common.create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {confirmDialog}
    </PageFrame>
  );
}
