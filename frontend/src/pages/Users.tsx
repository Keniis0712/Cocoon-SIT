import { useEffect, useMemo, useState } from "react";
import { isAxiosError } from "axios";
import { KeyRound, Plus, Search, ShieldCheck, UserRound, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { createAdminUser, listAdminUsers, updateAdminUser } from "@/api/admin-users";
import { listRoles } from "@/api/roles";
import type { AdminUserCreatePayload, AdminUserRead, AdminUserUpdatePayload, RoleRead } from "@/api/types";
import AccessCard from "@/components/AccessCard";
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

type UserFormState = {
  username: string;
  email: string;
  password: string;
  role: string;
  role_level: string;
  can_audit: boolean;
  parent_uid: string;
  is_active: boolean;
  invite_quota_remaining: string;
  invite_quota_unlimited: boolean;
};

const ALL_ROLES = "__all";
const NONE_PARENT = "__none";

const EMPTY_FORM: UserFormState = {
  username: "",
  email: "",
  password: "",
  role: "",
  role_level: "2",
  can_audit: false,
  parent_uid: NONE_PARENT,
  is_active: true,
  invite_quota_remaining: "0",
  invite_quota_unlimited: false,
};

function formatTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "-";
}

function parsePermissions(value: string) {
  try {
    const parsed = JSON.parse(value) as Record<string, unknown>;
    return Object.entries(parsed).filter(([, allowed]) => Boolean(allowed));
  } catch {
    return [] as Array<[string, unknown]>;
  }
}

function humanizePermission(key: string, t: (key: string) => string) {
  const mapping: Record<string, string> = {
    manage_users: t("me.capabilityUsers"),
    manage_system: t("me.capabilitySystem"),
    manage_providers: t("me.capabilityProviders"),
    manage_prompts: t("users.promptCapability"),
  };
  return mapping[key] || key;
}

function humanizeRoleDescription(role: RoleRead, t: (key: string, options?: Record<string, unknown>) => string) {
  const fallback = role.description || t("users.noRoleDescription");
  if (role.code === "admin") return t("users.systemRoleDescriptions.admin", { defaultValue: fallback });
  if (role.code === "reseller") return t("users.systemRoleDescriptions.reseller", { defaultValue: fallback });
  if (role.code === "user") return t("users.systemRoleDescriptions.user", { defaultValue: fallback });
  return fallback;
}

export default function UsersPage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const canManageUsers = Boolean(userInfo?.can_manage_users);
  const roleLevels = useMemo(
    () => [
      { value: "0", label: t("users.roleLevelValues.0") },
      { value: "1", label: t("users.roleLevelValues.1") },
      { value: "2", label: t("users.roleLevelValues.2") },
    ],
    [t],
  );

  const [users, setUsers] = useState<AdminUserRead[]>([]);
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(12);
  const [totalPages, setTotalPages] = useState(1);
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState(ALL_ROLES);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<AdminUserRead | null>(null);
  const [form, setForm] = useState<UserFormState>(EMPTY_FORM);

  useEffect(() => {
    if (!canManageUsers) {
      return;
    }

    async function bootstrap() {
      try {
        const roleResponse = await listRoles(1, 100);
        setRoles(roleResponse.items);
      } catch {
        toast.error(t("users.loadRolesFailed"));
      }
    }

    void bootstrap();
  }, [canManageUsers, t]);

  useEffect(() => {
    if (!canManageUsers) {
      return;
    }
    void fetchUsers();
  }, [canManageUsers, page, query, roleFilter]);

  async function fetchUsers() {
    setIsLoading(true);
    try {
      const response = await listAdminUsers(page, pageSize, {
        q: query.trim() || undefined,
        role: roleFilter === ALL_ROLES ? undefined : roleFilter,
      });
      setUsers(response.items);
      setTotalPages(response.total_pages || 1);
    } finally {
      setIsLoading(false);
    }
  }

  function openCreateDialog() {
    setEditing(null);
    setForm({
      ...EMPTY_FORM,
      role: roles[0]?.code || "user",
      role_level: "2",
      parent_uid: userInfo?.uid || NONE_PARENT,
    });
    setDialogOpen(true);
  }

  function openEditDialog(item: AdminUserRead) {
    setEditing(item);
    setForm({
      username: item.username,
      email: item.email || "",
      password: "",
      role: item.role,
      role_level: String(item.role_level),
      can_audit: item.can_audit,
      parent_uid: item.parent_uid || NONE_PARENT,
      is_active: item.is_active,
      invite_quota_remaining: String(item.invite_quota_remaining),
      invite_quota_unlimited: item.invite_quota_unlimited,
    });
    setDialogOpen(true);
  }

  async function saveUser() {
    setIsSaving(true);
    try {
      if (editing) {
        const payload: AdminUserUpdatePayload = {
          email: form.email.trim() || null,
          role: form.role,
          role_level: Number(form.role_level),
          can_audit: form.can_audit,
          is_active: form.is_active,
          password: form.password.trim() || undefined,
          invite_quota_remaining: Number(form.invite_quota_remaining || "0"),
          invite_quota_unlimited: form.invite_quota_unlimited,
        };
        await updateAdminUser(editing.uid, payload);
        toast.success(t("users.userUpdated"));
      } else {
        const payload: AdminUserCreatePayload = {
          username: form.username.trim(),
          email: form.email.trim() || null,
          password: form.password,
          role: form.role,
          role_level: Number(form.role_level),
          can_audit: form.can_audit,
          parent_uid: form.parent_uid === NONE_PARENT ? null : form.parent_uid,
          invite_quota_remaining: Number(form.invite_quota_remaining || "0"),
          invite_quota_unlimited: form.invite_quota_unlimited,
        };
        await createAdminUser(payload);
        toast.success(t("users.userCreated"));
      }

      setDialogOpen(false);
      setEditing(null);
      setForm(EMPTY_FORM);
      await fetchUsers();
    } catch (error) {
      if (isAxiosError(error)) {
        toast.error(String(error.response?.data?.detail || error.message));
      } else {
        toast.error(t(editing ? "users.updateFailed" : "users.createFailed"));
      }
    } finally {
      setIsSaving(false);
    }
  }

  const statsText = useMemo(() => {
    if (users.length === 0) {
      return t("users.emptyStats");
    }
    return t("users.pageStats", { page, totalPages, count: users.length });
  }, [page, t, totalPages, users.length]);

  const parentOptions = useMemo(() => {
    const map = new Map<string, AdminUserRead>();
    for (const item of users) {
      map.set(item.uid, item);
    }
    if (userInfo?.uid && !map.has(userInfo.uid)) {
      map.set(userInfo.uid, {
        uid: userInfo.uid,
        username: userInfo.username,
        email: null,
        parent_uid: userInfo.parent_uid,
        user_path: userInfo.user_path,
        invite_code: null,
        role: userInfo.role,
        role_level: userInfo.role_level,
        can_audit: userInfo.can_audit,
        is_active: true,
        token_version: 0,
        quota_tokens: 0,
        invite_quota_remaining: userInfo.invite_quota_remaining,
        invite_quota_unlimited: userInfo.invite_quota_unlimited,
        last_login_at: null,
        created_at: "",
        updated_at: "",
      });
    }
    return Array.from(map.values());
  }, [userInfo, users]);

  if (!canManageUsers) {
    return <AccessCard description={t("users.noPermission")} />;
  }

  return (
    <PageFrame
      title={t("users.title")}
      description={t("users.description")}
      actions={
        <Button onClick={openCreateDialog}>
          <Plus className="mr-2 size-4" />
          {t("users.newUser")}
        </Button>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-4">
          <Card className="border-border/70 bg-card/90">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Search className="size-4 text-primary" />
                {t("users.filters")}
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-[1fr_220px_auto] md:items-end">
              <div className="grid gap-2">
                <Label>{t("common.keyword")}</Label>
                <Input
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    setPage(1);
                  }}
                  placeholder={t("users.keywordPlaceholder")}
                />
              </div>
              <div className="grid gap-2">
                <Label>{t("common.role")}</Label>
                <Select
                  value={roleFilter}
                  onValueChange={(value) => {
                    setRoleFilter(value);
                    setPage(1);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t("users.allRoles")} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_ROLES}>{t("users.allRoles")}</SelectItem>
                    {roles.map((role) => (
                      <SelectItem key={role.code} value={role.code}>
                        {role.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button variant="outline" onClick={() => void fetchUsers()}>
                {t("users.refreshList")}
              </Button>
            </CardContent>
          </Card>

          <Card className="border-border/70 bg-card/90">
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Users className="size-4 text-primary" />
                    {t("users.list")}
                  </CardTitle>
                  <CardDescription>{statsText}</CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>
                    {t("common.previousPage")}
                  </Button>
                  <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>
                    {t("common.nextPage")}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {isLoading ? (
                <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("users.loading")}</div>
              ) : users.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("users.empty")}</div>
              ) : (
                users.map((item) => (
                  <div key={item.uid} className="rounded-2xl border border-border/70 bg-background/40 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 text-base font-semibold">
                          <UserRound className="size-4 text-primary" />
                          {item.username}
                        </div>
                        <div className="mt-1 break-all text-sm text-muted-foreground">{item.email || t("users.noEmail")}</div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <Badge variant="outline">{item.uid}</Badge>
                          <Badge>{item.role}</Badge>
                          <Badge variant="secondary">L{item.role_level}</Badge>
                          {item.can_audit ? <Badge variant="secondary">{t("users.canAudit")}</Badge> : null}
                          {item.is_active ? <Badge variant="secondary">{t("users.active")}</Badge> : <Badge variant="destructive">{t("users.inactive")}</Badge>}
                        </div>
                      </div>
                      <Button variant="outline" size="sm" onClick={() => openEditDialog(item)}>
                        {t("users.editUser")}
                      </Button>
                    </div>
                    <div className="mt-4 grid gap-3 text-sm text-muted-foreground md:grid-cols-2 xl:grid-cols-4">
                      <div>
                        <div className="text-xs uppercase tracking-wide">{t("users.parentUid")}</div>
                        <div className="mt-1 break-all text-foreground/90">{item.parent_uid || "-"}</div>
                      </div>
                      <div>
                        <div className="text-xs uppercase tracking-wide">{t("users.userPath")}</div>
                        <div className="mt-1 break-all text-foreground/90">{item.user_path}</div>
                      </div>
                      <div>
                        <div className="text-xs uppercase tracking-wide">{t("users.inviteQuota")}</div>
                        <div className="mt-1 text-foreground/90">
                          {item.invite_quota_unlimited ? t("users.unlimited") : item.invite_quota_remaining}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs uppercase tracking-wide">{t("users.lastLogin")}</div>
                        <div className="mt-1 text-foreground/90">{formatTime(item.last_login_at)}</div>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card className="border-border/70 bg-card/90">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <ShieldCheck className="size-4 text-primary" />
                {t("users.roleReference")}
              </CardTitle>
              <CardDescription>{t("users.roleReferenceDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {roles.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">{t("users.noRoles")}</div>
              ) : (
                roles.map((role) => {
                  const permissions = parsePermissions(role.permissions_json);
                  return (
                    <div key={role.code} className="rounded-2xl border border-border/70 p-4 text-sm">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <div className="font-medium">{role.name}</div>
                          <div className="mt-1 text-xs text-muted-foreground">{t("users.roleCode")}: {role.code}</div>
                        </div>
                        {role.is_system ? <Badge variant="outline">{t("users.systemRole")}</Badge> : <Badge variant="secondary">{t("users.customRole")}</Badge>}
                      </div>
                      <div className="mt-3 text-muted-foreground">{humanizeRoleDescription(role, t)}</div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {permissions.length > 0 ? (
                          permissions.map(([key]) => (
                            <Badge key={key} variant="secondary">
                              {humanizePermission(key, t)}
                            </Badge>
                          ))
                        ) : (
                          <Badge variant="outline">{t("users.basePermission")}</Badge>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </CardContent>
          </Card>

          <Card className="border-border/70 bg-card/90">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <KeyRound className="size-4 text-primary" />
                {t("users.policy")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <div className="rounded-xl border border-dashed border-border p-4">{t("users.policyLine1")}</div>
              <div className="rounded-xl border border-dashed border-border p-4">{t("users.policyLine2")}</div>
            </CardContent>
          </Card>
        </div>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? t("users.dialogEditTitle") : t("users.dialogCreateTitle")}</DialogTitle>
            <DialogDescription>
              {editing ? t("users.dialogEditDescription") : t("users.dialogCreateDescription")}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="admin-user-username">{t("me.username")}</Label>
                <Input
                  id="admin-user-username"
                  value={form.username}
                  disabled={Boolean(editing)}
                  onChange={(event) => setForm((prev) => ({ ...prev, username: event.target.value }))}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="admin-user-email">{t("common.email")}</Label>
                <Input
                  id="admin-user-email"
                  value={form.email}
                  placeholder={t("common.notSet")}
                  onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="grid gap-2">
                <Label>{t("common.role")}</Label>
                <Select value={form.role} onValueChange={(value) => setForm((prev) => ({ ...prev, role: value }))}>
                  <SelectTrigger>
                    <SelectValue placeholder={t("common.selectRole")} />
                  </SelectTrigger>
                  <SelectContent>
                    {roles.map((role) => (
                      <SelectItem key={role.code} value={role.code}>
                        {role.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>{t("users.roleLevel")}</Label>
                <Select value={form.role_level} onValueChange={(value) => setForm((prev) => ({ ...prev, role_level: value }))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {roleLevels.map((level) => (
                      <SelectItem key={level.value} value={level.value}>
                        {level.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="admin-user-password">{editing ? t("users.newPassword") : t("users.initialPassword")}</Label>
                <Input
                  id="admin-user-password"
                  type="password"
                  value={form.password}
                  placeholder={editing ? t("users.passwordPlaceholderEdit") : t("users.passwordPlaceholderCreate")}
                  onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
                />
              </div>
            </div>

            {!editing ? (
              <div className="grid gap-2">
                <Label>{t("users.parentUser")}</Label>
                <Select value={form.parent_uid} onValueChange={(value) => setForm((prev) => ({ ...prev, parent_uid: value }))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {userInfo?.can_manage_system ? <SelectItem value={NONE_PARENT}>{t("users.noParent")}</SelectItem> : null}
                    {parentOptions.map((item) => (
                      <SelectItem key={item.uid} value={item.uid}>
                        {item.username} · {item.uid}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : (
              <div className="grid gap-2">
                <Label>{t("users.parentUser")}</Label>
                <Input disabled value={editing.parent_uid || t("users.noParent")} />
              </div>
            )}

            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t("users.inviteQuota")}</Label>
                <Input
                  type="number"
                  min="0"
                  value={form.invite_quota_remaining}
                  disabled={form.invite_quota_unlimited}
                  onChange={(event) => setForm((prev) => ({ ...prev, invite_quota_remaining: event.target.value }))}
                />
              </div>
              <div className="grid gap-2">
                <Label>{t("users.userPath")}</Label>
                <Input disabled value={editing?.user_path || ""} placeholder={t("users.userPathPlaceholder")} />
              </div>
            </div>

            <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
              <Checkbox checked={form.can_audit} onCheckedChange={(checked) => setForm((prev) => ({ ...prev, can_audit: Boolean(checked) }))} />
              <span>{t("users.allowAudit")}</span>
            </label>
            <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
              <Checkbox checked={form.invite_quota_unlimited} onCheckedChange={(checked) => setForm((prev) => ({ ...prev, invite_quota_unlimited: Boolean(checked) }))} />
              <span>{t("users.unlimitedInviteQuota")}</span>
            </label>
            {editing ? (
              <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
                <Checkbox checked={form.is_active} onCheckedChange={(checked) => setForm((prev) => ({ ...prev, is_active: Boolean(checked) }))} />
                <span>{t("users.keepUserActive")}</span>
              </label>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              disabled={
                isSaving ||
                !form.role ||
                (!editing && (!form.username.trim() || form.password.length < 8)) ||
                Boolean(editing && form.password.length > 0 && form.password.length < 8)
              }
              onClick={saveUser}
            >
              {isSaving ? t("common.saving") : editing ? t("common.saveChanges") : t("users.newUser")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageFrame>
  );
}
