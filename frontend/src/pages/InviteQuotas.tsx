import { useEffect, useMemo, useState } from "react";
import { FolderTree, Pencil, UserRound } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { listAdminUsers } from "@/api/admin-users";
import { showErrorToast } from "@/api/client";
import { listGroups } from "@/api/groups";
import { listInviteQuotaAccounts, updateInviteQuota } from "@/api/invites";
import type { AdminUserRead, GroupRead, InviteQuotaAccountRead } from "@/api/types/access";
import { InvitesSubnav } from "@/components/composes/InvitesSubnav";
import { PopupSelect } from "@/components/composes/PopupSelect";
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

type TargetType = "USER" | "GROUP";

type QuotaFormState = {
  invite_quota_remaining: string;
  invite_quota_unlimited: boolean;
};

function formatTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "-";
}

function renderSummaryValue(t: (key: string) => string, summary: InviteQuotaAccountRead | null) {
  if (!summary) return "0";
  if (summary.invite_quota_unlimited) return t("invites.unlimited");
  return String(summary.invite_quota_remaining);
}

function MetricPanel({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-[28px] border border-border/70 bg-linear-to-br from-background via-background to-primary/5 p-5">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="mt-3 text-3xl font-semibold tracking-tight">{value}</div>
      {hint ? <div className="mt-2 text-xs text-muted-foreground">{hint}</div> : null}
    </div>
  );
}

export default function InviteQuotaPage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const canManageSystem = Boolean(userInfo?.can_manage_system);
  const [users, setUsers] = useState<AdminUserRead[]>([]);
  const [groups, setGroups] = useState<GroupRead[]>([]);
  const [accounts, setAccounts] = useState<InviteQuotaAccountRead[]>([]);
  const [targetType, setTargetType] = useState<TargetType>("USER");
  const [targetId, setTargetId] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [form, setForm] = useState<QuotaFormState>({
    invite_quota_remaining: "0",
    invite_quota_unlimited: false,
  });

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
  const userLabelMap = useMemo(
    () => new Map(users.map((item) => [item.uid, `${item.username} / ${item.uid}`])),
    [users],
  );
  const groupLabelMap = useMemo(
    () => new Map(groups.map((group) => [group.gid, `${group.name} / ${group.gid}`])),
    [groups],
  );
  const accountMap = useMemo(
    () => new Map(accounts.map((item) => [`${item.target_type}:${item.target_id}`, item])),
    [accounts],
  );
  const selectedAccount = useMemo(
    () => accountMap.get(`${targetType}:${targetId}`) || {
      target_type: targetType,
      target_id: targetId,
      invite_quota_remaining: 0,
      invite_quota_unlimited: false,
      updated_at: "",
    },
    [accountMap, targetId, targetType],
  );
  const totalUnlimitedTargets = useMemo(() => accounts.filter((item) => item.invite_quota_unlimited).length, [accounts]);

  useEffect(() => {
    void bootstrap();
  }, []);

  async function bootstrap() {
    try {
      const [usersResponse, groupsResponse, accountsResponse] = await Promise.all([
        listAdminUsers(1, 200),
        listGroups(1, 200),
        listInviteQuotaAccounts(),
      ]);
      setUsers(usersResponse.items);
      setGroups(groupsResponse.items);
      setAccounts(accountsResponse);
      setTargetId((prev) => prev || usersResponse.items[0]?.uid || groupsResponse.items[0]?.gid || "");
    } catch (error) {
      showErrorToast(error, t("invites.loadFailed"));
    }
  }

  function openEditDialog() {
    setForm({
      invite_quota_remaining: String(selectedAccount?.invite_quota_remaining || 0),
      invite_quota_unlimited: Boolean(selectedAccount?.invite_quota_unlimited),
    });
    setDialogOpen(true);
  }

  async function handleSaveQuota() {
    setIsSaving(true);
    try {
      await updateInviteQuota(targetType, targetId, {
        invite_quota_remaining: Number(form.invite_quota_remaining || "0"),
        invite_quota_unlimited: form.invite_quota_unlimited,
      });
      toast.success(t("invites.quotaUpdated"));
      setDialogOpen(false);
      await bootstrap();
    } catch (error) {
      showErrorToast(error, t("invites.quotaUpdateFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  const currentLabel =
    targetType === "USER"
      ? userLabelMap.get(targetId) || targetId || t("invites.noTargetSelected")
      : groupLabelMap.get(targetId) || targetId || t("invites.noTargetSelected");

  return (
    <PageFrame
      title={t("invites.summaryTitle")}
      description={t("invites.quotaManagementDescription")}
      actions={<InvitesSubnav />}
    >
      <div className="mb-6 grid gap-4 xl:grid-cols-3">
        <MetricPanel label={t("invites.personalQuota")} value={String(users.length)} hint={t("invites.typeUser")} />
        <MetricPanel label={t("invites.groupQuota")} value={String(groups.length)} hint={t("invites.typeGroup")} />
        <MetricPanel label={t("invites.unlimitedGrant")} value={String(totalUnlimitedTargets)} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <Card className="border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle className="text-base">{t("invites.summaryTitle")}</CardTitle>
            <CardDescription>{t("invites.quotaManagementDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label>{t("invites.targetType")}</Label>
              <Select
                value={targetType}
                onValueChange={(value) => {
                  const nextType = value as TargetType;
                  setTargetType(nextType);
                  setTargetId(nextType === "USER" ? users[0]?.uid || "" : groups[0]?.gid || "");
                }}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="USER">{t("invites.typeUser")}</SelectItem>
                  <SelectItem value="GROUP">{t("invites.typeGroup")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>{t("invites.targetId")}</Label>
              {targetType === "USER" ? (
                <PopupSelect
                  title={t("invites.selectUser")}
                  description={t("invites.quotaManagementDescription")}
                  placeholder={t("invites.selectUser")}
                  searchPlaceholder={t("common.search")}
                  emptyText={t("invites.noTargetSelected")}
                  value={targetId}
                  onValueChange={setTargetId}
                  options={userOptions}
                />
              ) : (
                <PopupSelect
                  title={t("invites.selectGroup")}
                  description={t("invites.quotaManagementDescription")}
                  placeholder={t("invites.selectGroup")}
                  searchPlaceholder={t("common.search")}
                  emptyText={t("invites.noTargetSelected")}
                  value={targetId}
                  onValueChange={setTargetId}
                  options={groupOptions}
                />
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              {targetType === "USER" ? <UserRound className="size-4 text-primary" /> : <FolderTree className="size-4 text-primary" />}
              {currentLabel}
            </CardTitle>
            <CardDescription>{t("invites.currentQuotaDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-2xl border border-border/70 p-4">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("invites.currentQuota")}</div>
                <div className="mt-2 font-medium">{renderSummaryValue(t, selectedAccount)}</div>
              </div>
              <div className="rounded-2xl border border-border/70 p-4">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("invites.targetType")}</div>
                <div className="mt-2 font-medium">{targetType === "USER" ? t("invites.typeUser") : t("invites.typeGroup")}</div>
              </div>
              <div className="rounded-2xl border border-border/70 p-4">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("common.updatedAt")}</div>
                <div className="mt-2 font-medium">{formatTime(selectedAccount?.updated_at)}</div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">{targetId || "-"}</Badge>
              {selectedAccount?.invite_quota_unlimited ? <Badge>{t("invites.unlimited")}</Badge> : null}
            </div>
            {canManageSystem ? (
              <div className="flex justify-end">
                <Button variant="outline" onClick={openEditDialog} disabled={!targetId}>
                  <Pencil className="mr-2 size-4" />
                  {t("invites.editQuota")}
                </Button>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{t("invites.editQuota")}</DialogTitle>
            <DialogDescription>{currentLabel}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>{t("invites.currentQuota")}</Label>
              <Input
                type="number"
                min="0"
                disabled={form.invite_quota_unlimited}
                value={form.invite_quota_remaining}
                onChange={(event) => setForm((prev) => ({ ...prev, invite_quota_remaining: event.target.value }))}
              />
            </div>
            <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
              <Checkbox
                checked={form.invite_quota_unlimited}
                onCheckedChange={(checked) => setForm((prev) => ({ ...prev, invite_quota_unlimited: Boolean(checked) }))}
              />
              <span>{t("invites.unlimitedGrant")}</span>
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>{t("common.cancel")}</Button>
            <Button disabled={isSaving || !targetId} onClick={() => void handleSaveQuota()}>
              {isSaving ? t("common.saving") : t("common.saveChanges")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageFrame>
  );
}
