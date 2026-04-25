import { useEffect, useMemo, useState } from "react";
import { Gift, Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { listAdminUsers } from "@/api/admin-users";
import { showErrorToast } from "@/api/client";
import { listGroups } from "@/api/groups";
import { createInviteGrant, listInviteGrants } from "@/api/invites";
import type { AdminUserRead, GroupRead, InviteQuotaGrantCreatePayload, InviteQuotaGrantRead } from "@/api/types/access";
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

function inviteTypeLabel(type: string, t: (key: string) => string) {
  if (type === "USER") return t("invites.typeUser");
  if (type === "GROUP") return t("invites.typeGroup");
  return type;
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

export default function InviteGrantHistoryPage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const [users, setUsers] = useState<AdminUserRead[]>([]);
  const [groups, setGroups] = useState<GroupRead[]>([]);
  const [grants, setGrants] = useState<InviteQuotaGrantRead[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [form, setForm] = useState<InviteGrantForm>({
    target_type: "USER",
    target_id: "",
    amount: "1",
    is_unlimited: false,
    note: "",
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
  const activeGrantCount = useMemo(() => grants.filter((grant) => !grant.revoked_at).length, [grants]);
  const unlimitedGrantCount = useMemo(() => grants.filter((grant) => grant.is_unlimited).length, [grants]);

  useEffect(() => {
    void bootstrap();
  }, []);

  async function bootstrap() {
    try {
      const [usersResponse, groupsResponse, grantsResponse] = await Promise.all([
        listAdminUsers(1, 200),
        listGroups(1, 200),
        listInviteGrants(1, 200),
      ]);
      setUsers(usersResponse.items);
      setGroups(groupsResponse.items);
      setGrants(grantsResponse.items);
      setForm((prev) => ({
        ...prev,
        target_id: prev.target_id || userInfo?.uid || usersResponse.items[0]?.uid || groupsResponse.items[0]?.gid || "",
      }));
    } catch (error) {
      showErrorToast(error, t("invites.loadFailed"));
    }
  }

  async function handleCreateGrant() {
    setIsSaving(true);
    try {
      const payload: InviteQuotaGrantCreatePayload = {
        target_type: form.target_type,
        target_id: form.target_id,
        amount: Number(form.amount || "0"),
        is_unlimited: form.is_unlimited,
        note: form.note.trim() || undefined,
      };
      await createInviteGrant(payload);
      toast.success(t("invites.grantCreated"));
      setDialogOpen(false);
      await bootstrap();
    } catch (error) {
      showErrorToast(error, t("invites.grantCreateFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <PageFrame
      title={t("invites.grantsTitle")}
      description={t("invites.grantsDescription")}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <InvitesSubnav />
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="mr-2 size-4" />
            {t("invites.newGrant")}
          </Button>
        </div>
      }
    >
      <div className="mb-6 grid gap-4 xl:grid-cols-3">
        <MetricPanel label={t("invites.grantsTitle")} value={String(grants.length)} />
        <MetricPanel label={t("invites.activeQuotaRecords")} value={String(activeGrantCount)} />
        <MetricPanel label={t("invites.unlimitedGrant")} value={String(unlimitedGrantCount)} />
      </div>

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
              <div key={grant.id} className="rounded-[24px] border border-border/70 bg-background/30 p-4 text-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="font-medium">
                      {inviteTypeLabel(grant.target_type, t)} /{" "}
                      {grant.target_type === "USER"
                        ? userLabelMap.get(grant.target_id) || grant.target_id
                        : groupLabelMap.get(grant.target_id) || grant.target_id}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{userLabelMap.get(grant.granter_uid) || grant.granter_uid || "-"}</div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="outline">
                      {grant.is_unlimited ? t("invites.unlimitedGrant") : t("invites.finiteGrant", { amount: grant.amount })}
                    </Badge>
                    {grant.revoked_at ? <Badge variant="secondary">{t("invites.revokedGrant")}</Badge> : null}
                  </div>
                </div>
                <div className="mt-3 grid gap-1 text-xs text-muted-foreground">
                  <div>{grant.note || "-"}</div>
                  <div>{formatTime(grant.created_at)}</div>
                  {grant.revoked_at ? <div>{t("invites.revokedAt")}: {formatTime(grant.revoked_at)}</div> : null}
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
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
                  value={form.target_type}
                  onValueChange={(value) =>
                    setForm((prev) => ({
                      ...prev,
                      target_type: value as InviteGrantForm["target_type"],
                      target_id: value === "USER" ? userInfo?.uid || users[0]?.uid || "" : groups[0]?.gid || "",
                    }))
                  }
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
                {form.target_type === "USER" ? (
                  <PopupSelect
                    title={t("invites.selectUser")}
                    placeholder={t("invites.selectUser")}
                    searchPlaceholder={t("common.search")}
                    emptyText={t("invites.noGrants")}
                    value={form.target_id}
                    onValueChange={(value) => setForm((prev) => ({ ...prev, target_id: value }))}
                    options={userOptions}
                  />
                ) : (
                  <PopupSelect
                    title={t("invites.selectGroup")}
                    placeholder={t("invites.selectGroup")}
                    searchPlaceholder={t("common.search")}
                    emptyText={t("invites.noGroupSelected")}
                    value={form.target_id}
                    onValueChange={(value) => setForm((prev) => ({ ...prev, target_id: value }))}
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
                  value={form.amount}
                  disabled={form.is_unlimited}
                  onChange={(event) => setForm((prev) => ({ ...prev, amount: event.target.value }))}
                />
              </div>
              <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
                <Checkbox checked={form.is_unlimited} onCheckedChange={(checked) => setForm((prev) => ({ ...prev, is_unlimited: Boolean(checked) }))} />
                <span>{t("invites.unlimitedGrant")}</span>
              </label>
            </div>
            <div className="grid gap-2">
              <Label>{t("invites.note")}</Label>
              <Input value={form.note} onChange={(event) => setForm((prev) => ({ ...prev, note: event.target.value }))} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>{t("common.cancel")}</Button>
            <Button
              disabled={isSaving || !form.target_id || (!form.is_unlimited && Number(form.amount || "0") < 1)}
              onClick={() => void handleCreateGrant()}
            >
              {isSaving ? t("common.saving") : t("common.create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageFrame>
  );
}
