import { useEffect, useMemo, useState } from "react";
import { Copy, LogOut, Save, Shield, User } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { showErrorToast } from "@/api/client";
import {
  buildSessionPatch,
  createImBindToken,
  logout,
  me,
  updateMyProfile,
} from "@/api/user";
import { PopupSelect } from "@/components/composes/PopupSelect";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { copyTextToClipboard } from "@/lib/clipboard";
import { buildTimezoneOptions, resolveBrowserTimezone } from "@/lib/timezones";
import { useUserStore } from "@/store/useUserStore";

export default function MePage() {
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);
  const updateInfo = useUserStore((state) => state.updateInfo);
  const clearSession = useUserStore((state) => state.logout);
  const [email, setEmail] = useState<string | null>(null);
  const [createdAt, setCreatedAt] = useState<string | null>(null);
  const [timezone, setTimezone] = useState(userInfo?.timezone || "UTC");
  const [isSaving, setIsSaving] = useState(false);
  const [bindToken, setBindToken] = useState("");
  const [bindTokenExpiresAt, setBindTokenExpiresAt] = useState<string | null>(null);
  const [isCreatingBindToken, setIsCreatingBindToken] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const browserTimezone = useMemo(() => resolveBrowserTimezone(), []);
  const timezoneOptions = useMemo(
    () =>
      buildTimezoneOptions({
        browserTimezone,
        currentTimezone: timezone,
      }),
    [browserTimezone, timezone],
  );

  useEffect(() => {
    async function refreshProfile() {
      if (!userInfo) {
        return;
      }
      try {
        const profile = await me();
        updateInfo(buildSessionPatch(profile));
        setEmail(profile.email);
        setCreatedAt(profile.created_at);
        setTimezone(profile.timezone);
      } catch {
        // Keep the existing session info if background refresh fails.
      }
    }

    void refreshProfile();
  }, [updateInfo, userInfo?.uid]);

  useEffect(() => {
    if (!bindTokenExpiresAt) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      setNowMs(Date.now());
    }, 1000);
    return () => window.clearInterval(timer);
  }, [bindTokenExpiresAt]);

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

  const bindTokenSecondsRemaining = useMemo(() => {
    if (!bindTokenExpiresAt) {
      return 0;
    }
    const diffMs = new Date(bindTokenExpiresAt).getTime() - nowMs;
    return Math.max(0, Math.ceil(diffMs / 1000));
  }, [bindTokenExpiresAt, nowMs]);

  const bindTokenExpired = Boolean(bindTokenExpiresAt) && bindTokenSecondsRemaining <= 0;
  const bindTokenCountdownText = !bindToken
    ? ""
    : bindTokenExpired
      ? t("me.imBindExpired")
      : t("me.imBindCountdown", { count: bindTokenSecondsRemaining });

  async function saveProfile() {
    if (!userInfo) {
      return;
    }

    setIsSaving(true);
    try {
      if (timezone !== (userInfo.timezone || "UTC")) {
        const profile = await updateMyProfile({ timezone });
        updateInfo(buildSessionPatch(profile));
        setEmail(profile.email);
        setCreatedAt(profile.created_at);
        setTimezone(profile.timezone);
      }
      toast.success(t("me.saveSuccess"));
    } catch (error) {
      showErrorToast(error, t("me.saveFailed"));
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

  async function handleCreateBindToken() {
    setIsCreatingBindToken(true);
    try {
      const payload = await createImBindToken();
      setBindToken(payload.token);
      setBindTokenExpiresAt(payload.expires_at);
      setNowMs(Date.now());
      toast.success(t("me.imBindTokenCreated"));
    } catch (error) {
      showErrorToast(error, t("me.imBindTokenCreateFailed"));
    } finally {
      setIsCreatingBindToken(false);
    }
  }

  async function handleCopyBindToken() {
    if (!bindToken) {
      return;
    }
    try {
      await copyTextToClipboard(bindToken);
      toast.success(t("me.imBindTokenCopied"));
    } catch (error) {
      showErrorToast(error, t("me.imBindTokenCopyFailed"));
    }
  }

  return (
    <PageFrame title={t("me.title")} description={t("me.description")}>
      <div className="grid gap-6">
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
                  {userInfo?.role || "-"} / L{userInfo?.role_level ?? "-"}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">{t("me.timezone")}</div>
                <div className="mt-1 font-medium">{userInfo?.timezone || "UTC"}</div>
              </div>
              <div>
                <div className="text-muted-foreground">{t("me.userUid")}</div>
                <div className="mt-1 font-medium break-all">{userInfo?.uid || "-"}</div>
              </div>
              <div>
                <div className="mb-2 text-muted-foreground">{t("me.capabilities")}</div>
                <div className="flex flex-wrap gap-2">
                  {badges.length > 0 ? (
                    badges.map((badge) => <Badge key={badge}>{badge}</Badge>)
                  ) : (
                    <Badge variant="secondary">{t("me.normalUser")}</Badge>
                  )}
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
                  <Input value={userInfo?.username || ""} disabled />
                </div>
                <div className="grid gap-2">
                  <Label>{t("common.email")}</Label>
                  <Input value={email || ""} disabled placeholder={t("common.notSet")} />
                </div>
              </div>
              <div className="grid gap-2">
                <Label>{t("me.timezone")}</Label>
                <PopupSelect
                  title={t("me.timezone")}
                  description={t("me.profileDescription")}
                  placeholder={browserTimezone}
                  searchPlaceholder={t("common.search")}
                  emptyText={t("common.notSet")}
                  value={timezone}
                  onValueChange={setTimezone}
                  options={timezoneOptions}
                  pageSize={12}
                />
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <Badge variant="outline" className="font-normal">
                    {timezone}
                  </Badge>
                  {browserTimezone !== timezone ? (
                    <Badge variant="secondary" className="font-normal">
                      {browserTimezone}
                    </Badge>
                  ) : null}
                </div>
              </div>
              <div className="grid gap-2">
                <Label>{t("common.createdAt")}</Label>
                <Input value={createdAt ? new Date(createdAt).toLocaleString() : ""} disabled placeholder="-" />
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
              </div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{t("me.imBindTitle")}</CardTitle>
            <CardDescription>{t("me.imBindDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-2 md:grid-cols-[1.5fr_220px]">
              <div className="grid gap-2">
                <Label>{t("me.imBindToken")}</Label>
                <div className="flex gap-2">
                  <Input value={bindToken} disabled placeholder={t("me.imBindTokenPlaceholder")} />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={handleCopyBindToken}
                    disabled={!bindToken}
                    aria-label={t("me.imBindCopy")}
                    title={t("me.imBindCopy")}
                  >
                    <Copy className="size-4" />
                  </Button>
                </div>
              </div>
              <div className="grid gap-2">
                <Label>{t("me.imBindCountdownLabel", { defaultValue: "Expires In" })}</Label>
                <Input
                  value={bindTokenCountdownText}
                  disabled
                  placeholder="-"
                />
              </div>
            </div>
            <div className={`text-sm ${bindTokenExpired ? "text-destructive" : "text-muted-foreground"}`}>
              {!bindToken
                ? t("me.imBindHint")
                : bindTokenExpired
                  ? t("me.imBindExpired")
                  : t("me.imBindCountdown", { count: bindTokenSecondsRemaining })}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button disabled={isCreatingBindToken} onClick={handleCreateBindToken}>
                {isCreatingBindToken
                  ? t("common.loading")
                  : bindToken
                    ? t("me.imBindRegenerate")
                    : t("me.imBindGenerate")}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </PageFrame>
  );
}
