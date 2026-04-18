import { useEffect, useMemo, useState } from "react";
import { KeyRound, LogOut, Save, Shield, User } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { changePassword, changeUsername, logout, me } from "@/api/user";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useUserStore } from "@/store/useUserStore";

export default function MePage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const updateInfo = useUserStore((state) => state.updateInfo);
  const clearSession = useUserStore((state) => state.logout);
  const [username, setUsername] = useState(userInfo?.username || "");
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [email, setEmail] = useState<string | null>(null);
  const [createdAt, setCreatedAt] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    async function refreshProfile() {
      if (!userInfo) {
        return;
      }
      try {
        const profile = await me();
        updateInfo({
          uid: profile.uid,
          username: profile.username,
          parent_uid: profile.parent_uid,
          user_path: profile.user_path,
          role: profile.role,
          role_level: profile.role_level,
          can_audit: profile.can_audit,
          can_manage_system: profile.can_manage_system,
          can_manage_users: profile.can_manage_users,
          can_manage_prompts: profile.can_manage_prompts,
          can_manage_providers: profile.can_manage_providers,
          invite_quota_remaining: profile.invite_quota_remaining,
          invite_quota_unlimited: profile.invite_quota_unlimited,
        });
        setUsername(profile.username);
        setEmail(profile.email);
        setCreatedAt(profile.created_at);
      } catch {
        // Keep the existing session info if background refresh fails.
      }
    }

    void refreshProfile();
  }, [updateInfo, userInfo?.uid]);

  const badges = useMemo(
    () =>
      [
        userInfo?.can_manage_system ? t("me.capabilitySystem") : null,
        userInfo?.can_manage_users ? t("me.capabilityUsers") : null,
        userInfo?.can_manage_providers ? t("me.capabilityProviders") : null,
        userInfo?.can_audit ? t("me.capabilityAudit") : null,
      ].filter(Boolean) as string[],
    [t, userInfo],
  );

  async function saveProfile() {
    if (!userInfo) {
      return;
    }

    setIsSaving(true);
    try {
      if (username.trim() && username.trim() !== userInfo.username) {
        const profile = await changeUsername(username.trim());
        updateInfo({
          uid: profile.uid,
          username: profile.username,
          parent_uid: profile.parent_uid,
          user_path: profile.user_path,
          role: profile.role,
          role_level: profile.role_level,
          can_audit: profile.can_audit,
          can_manage_system: profile.can_manage_system,
          can_manage_users: profile.can_manage_users,
          can_manage_prompts: profile.can_manage_prompts,
          can_manage_providers: profile.can_manage_providers,
          invite_quota_remaining: profile.invite_quota_remaining,
          invite_quota_unlimited: profile.invite_quota_unlimited,
        });
        setEmail(profile.email);
        setCreatedAt(profile.created_at);
      }

      if (oldPassword && newPassword) {
        await changePassword(oldPassword, newPassword);
        setOldPassword("");
        setNewPassword("");
      }

      toast.success(t("me.saveSuccess"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("me.saveFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleLogout() {
    try {
      if (userInfo?.refresh_token) {
        await logout(userInfo.refresh_token);
      }
    } catch {
      // Ignore logout request failures.
    } finally {
      clearSession();
      window.location.href = "/login";
    }
  }

  return (
    <PageFrame title={t("me.title")} description={t("me.description")}>
      <div className="grid gap-6 xl:grid-cols-[1fr_1.2fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="size-4 text-primary" />
              {t("me.overview")}
            </CardTitle>
            <CardDescription>{t("me.overviewDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div>
              <div className="text-muted-foreground">{t("me.username")}</div>
              <div className="mt-1 font-medium">{userInfo?.username || "-"}</div>
            </div>
            <div>
              <div className="text-muted-foreground">{t("me.role")}</div>
              <div className="mt-1 font-medium">
                {userInfo?.role || "-"} · L{userInfo?.role_level ?? "-"}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">{t("me.userUid")}</div>
              <div className="mt-1 font-medium break-all">{userInfo?.uid || "-"}</div>
            </div>
            <div>
              <div className="text-muted-foreground">{t("me.parentUid")}</div>
              <div className="mt-1 font-medium break-all">{userInfo?.parent_uid || "-"}</div>
            </div>
            <div>
              <div className="text-muted-foreground">{t("me.userPath")}</div>
              <div className="mt-1 font-medium break-all">{userInfo?.user_path || "-"}</div>
            </div>
            <div>
              <div className="text-muted-foreground">{t("me.inviteQuota")}</div>
              <div className="mt-1 font-medium">
                {userInfo?.invite_quota_unlimited ? t("me.unlimitedQuota") : userInfo?.invite_quota_remaining ?? 0}
              </div>
            </div>
            <div>
              <div className="mb-2 text-muted-foreground">{t("me.capabilities")}</div>
              <div className="flex flex-wrap gap-2">
                {badges.length > 0 ? badges.map((badge) => <Badge key={badge}>{badge}</Badge>) : <Badge variant="secondary">{t("me.normalUser")}</Badge>}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="size-4 text-primary" />
              {t("me.profile")}
            </CardTitle>
            <CardDescription>{t("me.profileDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-2 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t("me.username")}</Label>
                <Input value={username} onChange={(event) => setUsername(event.target.value)} />
              </div>
              <div className="grid gap-2">
                <Label>{t("common.email")}</Label>
                <Input value={email || ""} disabled placeholder={t("common.notSet")} />
              </div>
            </div>
            <div className="grid gap-2">
              <Label>{t("common.createdAt")}</Label>
              <Input value={createdAt ? new Date(createdAt).toLocaleString() : ""} disabled placeholder="-" />
            </div>
            <div className="grid gap-2 md:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="profile-old-password">{t("me.oldPassword")}</Label>
                <Input id="profile-old-password" type="password" value={oldPassword} onChange={(event) => setOldPassword(event.target.value)} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="profile-new-password">{t("me.newPassword")}</Label>
                <Input id="profile-new-password" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button disabled={isSaving} onClick={saveProfile}>
                <Save className="mr-2 size-4" />
                {isSaving ? t("common.saving") : t("common.saveChanges")}
              </Button>
              <Button variant="outline" onClick={handleLogout}>
                <LogOut className="mr-2 size-4" />
                {t("nav.logout")}
              </Button>
              <Button variant="secondary" disabled>
                <KeyRound className="mr-2 size-4" />
                {t("me.currentPort")}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </PageFrame>
  );
}
