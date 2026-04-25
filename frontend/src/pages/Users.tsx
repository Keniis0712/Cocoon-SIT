import { useEffect, useMemo, useState } from "react";
import { Plus, Search, ShieldCheck, UserRound, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { createAdminUser, listAdminUsers, updateAdminUser } from "@/api/admin-users";
import { showErrorToast } from "@/api/client";
import { listRoles } from "@/api/roles";
import type { AdminUserCreatePayload, AdminUserRead, AdminUserUpdatePayload, RoleRead } from "@/api/types/access";
import AccessCard from "@/components/AccessCard";
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
import { groupPermissions, listKnownPermissions, permissionLabel } from "@/lib/permission-catalog";
import { useUserStore } from "@/store/useUserStore";

type UserFormState = {
  username: string;
  email: string;
  password: string;
  role: string;
  permissions_json: Record<string, boolean>;
  is_active: boolean;
};

type PermissionMode = "inherit" | "allow" | "deny";

const ALL_ROLES = "__all";
const NO_ROLE = "__none";

const EMPTY_FORM: UserFormState = {
  username: "",
  email: "",
  password: "",
  role: NO_ROLE,
  permissions_json: {},
  is_active: true,
};

function formatTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "-";
}

function parsePermissions(value: string) {
  try {
    const parsed = JSON.parse(value) as Record<string, unknown>;
    return Object.entries(parsed).filter(([, allowed]) => Boolean(allowed)).map(([key]) => key);
  } catch {
    return [] as string[];
  }
}

function roleValue(roleName: string | null | undefined) {
  return roleName || NO_ROLE;
}

function humanizeRoleDescription(role: RoleRead, t: (key: string, options?: Record<string, unknown>) => string) {
  const fallback = role.description || t("users.noRoleDescription");
  if (role.code === "admin") return t("users.systemRoleDescriptions.admin", { defaultValue: fallback });
  if (role.code === "operator") return t("users.systemRoleDescriptions.operator", { defaultValue: fallback });
  if (role.code === "user") return t("users.systemRoleDescriptions.user", { defaultValue: fallback });
  return fallback;
}

export default function UsersPage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const canManageUsers = Boolean(userInfo?.can_manage_users);

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
  const isEditingSelf = Boolean(editing && userInfo?.uid && editing.uid === userInfo.uid);

  useEffect(() => {
    if (!canManageUsers) return;
    void (async () => {
      try {
        const roleResponse = await listRoles(1, 100);
        setRoles(roleResponse.items);
      } catch (error) {
        showErrorToast(error, t("users.loadRolesFailed"));
      }
    })();
  }, [canManageUsers, t]);

  useEffect(() => {
    if (!canManageUsers) return;
    void fetchUsers();
  }, [canManageUsers, page, query, roleFilter]);

  const currentRole = useMemo(
    () => roles.find((role) => role.name === (form.role === NO_ROLE ? null : form.role)) ?? null,
    [form.role, roles],
  );

  const knownPermissionKeys = useMemo(() => {
    const fromRoles = roles.flatMap((role) => parsePermissions(role.permissions_json));
    const fromUsers = users.flatMap((user) => [
      ...Object.keys(user.permissions_json || {}),
      ...Object.keys(user.effective_permissions || {}),
    ]);
    const fromCurrentUser = Object.keys(userInfo?.permissions || {});
    return listKnownPermissions([...fromRoles, ...fromUsers, ...fromCurrentUser]);
  }, [roles, users, userInfo?.permissions]);

  const permissionGroups = useMemo(() => groupPermissions(knownPermissionKeys), [knownPermissionKeys]);
  const roleOptions = useMemo(
    () => [
      { value: ALL_ROLES, label: t("users.allRoles"), description: t("users.roleReferenceDescription") },
      ...roles.map((role) => ({
        value: role.name,
        label: role.name,
        description: humanizeRoleDescription(role, t),
        keywords: [role.code],
      })),
    ],
    [roles, t],
  );
  const assignableRoleOptions = useMemo(
    () => [
      { value: NO_ROLE, label: t("users.noRoleAssigned"), description: t("users.noRoleDescription") },
      ...roles.map((role) => ({
        value: role.name,
        label: role.name,
        description: humanizeRoleDescription(role, t),
        keywords: [role.code],
      })),
    ],
    [roles, t],
  );

  const currentRolePermissions = useMemo(() => {
    if (!currentRole) return {} as Record<string, boolean>;
    return Object.fromEntries(parsePermissions(currentRole.permissions_json).map((key) => [key, true]));
  }, [currentRole]);

  const directPermissionCount = useMemo(
    () => Object.values(form.permissions_json).filter((value) => value === true).length,
    [form.permissions_json],
  );

  const deniedPermissionCount = useMemo(
    () => Object.values(form.permissions_json).filter((value) => value === false).length,
    [form.permissions_json],
  );

  const effectivePermissionCount = useMemo(
    () =>
      knownPermissionKeys.filter((key) =>
        form.permissions_json[key] !== undefined ? form.permissions_json[key] : Boolean(currentRolePermissions[key]),
      ).length,
    [currentRolePermissions, form.permissions_json, knownPermissionKeys],
  );

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
      role: roleValue(roles.find((role) => role.code === "user")?.name ?? roles[0]?.name ?? null),
      permissions_json: {},
      is_active: true,
    });
    setDialogOpen(true);
  }

  function openEditDialog(item: AdminUserRead) {
    setEditing(item);
    setForm({
      username: item.username,
      email: item.email || "",
      password: "",
      role: roleValue(item.role),
      permissions_json: { ...(item.permissions_json || {}) },
      is_active: item.is_active,
    });
    setDialogOpen(true);
  }

  function permissionMode(key: string): PermissionMode {
    const value = form.permissions_json[key];
    if (value === true) return "allow";
    if (value === false) return "deny";
    return "inherit";
  }

  function setPermissionMode(key: string, value: PermissionMode) {
    setForm((prev) => {
      const permissions_json = { ...prev.permissions_json };
      if (value === "inherit") {
        delete permissions_json[key];
      } else {
        permissions_json[key] = value === "allow";
      }
      return { ...prev, permissions_json };
    });
  }

  async function saveUser() {
    setIsSaving(true);
    try {
      if (editing) {
        const payload: AdminUserUpdatePayload = {
          email: form.email.trim() || null,
          role: form.role === NO_ROLE ? null : form.role,
          permissions_json: form.permissions_json,
          is_active: form.is_active,
          password: form.password.trim() || undefined,
        };
        await updateAdminUser(editing.uid, payload);
        toast.success(t("users.userUpdated"));
      } else {
        const payload: AdminUserCreatePayload = {
          username: form.username.trim(),
          email: form.email.trim() || null,
          password: form.password,
          role: form.role === NO_ROLE ? null : form.role,
          permissions_json: form.permissions_json,
          role_level: 2,
          can_audit: false,
        };
        await createAdminUser(payload);
        toast.success(t("users.userCreated"));
      }

      setDialogOpen(false);
      setEditing(null);
      setForm(EMPTY_FORM);
      await fetchUsers();
    } catch (error) {
      showErrorToast(error, t(editing ? "users.updateFailed" : "users.createFailed"));
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
                <PopupSelect
                  title={t("common.role")}
                  description={t("users.roleReferenceDescription")}
                  placeholder={t("users.allRoles")}
                  searchPlaceholder={t("common.search")}
                  emptyText={t("users.noRoles")}
                  value={roleFilter}
                  onValueChange={(value) => {
                    setRoleFilter(value);
                    setPage(1);
                  }}
                  options={roleOptions}
                />
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
                users.map((item) => {
                  const effectivePermissions = Object.entries(item.effective_permissions || {}).filter(([, allowed]) => allowed);
                  return (
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
                            <Badge>{item.role || t("users.noRoleAssigned")}</Badge>
                            {item.can_audit ? <Badge variant="secondary">{t("users.canAudit")}</Badge> : null}
                            {Object.keys(item.permissions_json || {}).length > 0 ? (
                              <Badge variant="outline">
                                {t("users.directPermissionCount", { count: Object.keys(item.permissions_json).length })}
                              </Badge>
                            ) : null}
                            <Badge variant="secondary">
                              {t("users.effectivePermissionCount", { count: effectivePermissions.length })}
                            </Badge>
                            {item.is_active ? (
                              <Badge variant="secondary">{t("users.active")}</Badge>
                            ) : (
                              <Badge variant="destructive">{t("users.inactive")}</Badge>
                            )}
                          </div>
                        </div>
                        <Button variant="outline" size="sm" onClick={() => openEditDialog(item)}>
                          {t("users.editUser")}
                        </Button>
                      </div>
                      <div className="mt-4 grid gap-3 text-sm text-muted-foreground md:grid-cols-2 xl:grid-cols-3">
                        <div>
                          <div className="text-xs uppercase tracking-wide">{t("common.createdAt")}</div>
                          <div className="mt-1 text-foreground/90">{formatTime(item.created_at)}</div>
                        </div>
                        <div>
                          <div className="text-xs uppercase tracking-wide">{t("common.status")}</div>
                          <div className="mt-1 text-foreground/90">
                            {item.is_active ? t("users.active") : t("users.inactive")}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs uppercase tracking-wide">{t("common.role")}</div>
                          <div className="mt-1 text-foreground/90">{item.role || t("users.noRoleAssigned")}</div>
                        </div>
                        <div className="md:col-span-2 xl:col-span-3">
                          <div className="text-xs uppercase tracking-wide">{t("users.effectivePermissions")}</div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {effectivePermissions.length > 0 ? (
                              effectivePermissions.map(([key]) => (
                                <Badge key={key} variant="secondary">
                                  {permissionLabel(key)}
                                </Badge>
                              ))
                            ) : (
                              <Badge variant="outline">{t("users.noEffectivePermissions")}</Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })
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
                          <div className="mt-1 text-xs text-muted-foreground">
                            {t("users.roleCode")}: {role.code}
                          </div>
                        </div>
                        {role.is_system ? (
                          <Badge variant="outline">{t("users.systemRole")}</Badge>
                        ) : (
                          <Badge variant="secondary">{t("users.customRole")}</Badge>
                        )}
                      </div>
                      <div className="mt-3 text-muted-foreground">{humanizeRoleDescription(role, t)}</div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {permissions.length > 0 ? (
                          permissions.map((key) => (
                            <Badge key={key} variant="secondary">
                              {permissionLabel(key)}
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
        </div>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-5xl">
          <DialogHeader>
            <DialogTitle>{editing ? t("users.dialogEditTitle") : t("users.dialogCreateTitle")}</DialogTitle>
            <DialogDescription>
              {editing ? t("users.dialogEditDescription") : t("users.dialogCreateDescription")}
            </DialogDescription>
          </DialogHeader>
          <div className="grid max-h-[70vh] gap-4 overflow-y-auto py-2 pr-1">
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

            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t("common.role")}</Label>
                <PopupSelect
                  title={t("common.role")}
                  description={t("users.dialogEditDescription")}
                  placeholder={t("common.selectRole")}
                  searchPlaceholder={t("common.search")}
                  emptyText={t("users.noRoles")}
                  value={form.role}
                  disabled={isEditingSelf}
                  onValueChange={(value) => setForm((prev) => ({ ...prev, role: value }))}
                  options={assignableRoleOptions}
                />
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

            <div className="grid gap-3 rounded-xl border border-border/70 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="font-medium">{t("users.permissionOverridesTitle")}</div>
                  <div className="mt-1 text-sm text-muted-foreground">{t("users.permissionOverridesDescription")}</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">{t("users.directPermissionCount", { count: directPermissionCount })}</Badge>
                  <Badge variant="outline">{t("users.deniedPermissionCount", { count: deniedPermissionCount })}</Badge>
                  <Badge>{t("users.effectivePermissionCount", { count: effectivePermissionCount })}</Badge>
                </div>
              </div>

              {permissionGroups.map((group) => (
                <div key={group.resource} className="rounded-xl border border-border/60 p-3">
                  <div className="mb-3 font-medium">{group.label}</div>
                  <div className="grid gap-3">
                    {group.permissions.map((key) => {
                      const baseAllowed = Boolean(currentRolePermissions[key]);
                      const mode = permissionMode(key);
                      const effectiveAllowed = mode === "inherit" ? baseAllowed : mode === "allow";
                      return (
                        <div
                          key={key}
                          className="grid gap-2 rounded-lg border border-border/50 p-3 md:grid-cols-[1fr_180px_auto] md:items-center"
                        >
                          <div>
                            <div className="font-medium">{permissionLabel(key)}</div>
                            <div className="mt-1 text-xs text-muted-foreground">
                              {baseAllowed ? t("users.inheritedFromRole") : t("users.notGrantedByRole")}
                            </div>
                          </div>
                          <Select
                            value={mode}
                            disabled={isEditingSelf}
                            onValueChange={(value) => setPermissionMode(key, value as PermissionMode)}
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="inherit">{t("users.permissionModeInherit")}</SelectItem>
                              <SelectItem value="allow">{t("users.permissionModeAllow")}</SelectItem>
                              <SelectItem value="deny">{t("users.permissionModeDeny")}</SelectItem>
                            </SelectContent>
                          </Select>
                          <Badge variant={effectiveAllowed ? "secondary" : "outline"}>
                            {effectiveAllowed ? t("users.permissionEffectiveAllow") : t("users.permissionEffectiveDeny")}
                          </Badge>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>

            {editing ? (
              <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
                <Checkbox
                  checked={form.is_active}
                  disabled={isEditingSelf}
                  onCheckedChange={(checked) => setForm((prev) => ({ ...prev, is_active: Boolean(checked) }))}
                />
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
