import { useEffect, useMemo, useState } from "react";
import { Languages, MoonStar, RefreshCcw, Save } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { showErrorToast } from "@/api/client";
import { cleanupExpiredArtifacts } from "@/api/adminArtifacts";
import { listModelProviders } from "@/api/providers";
import { listPromptTemplates } from "@/api/prompts";
import { getSystemSettings, updateSystemSettings } from "@/api/settings";
import type { ModelProviderRead } from "@/api/types/providers";
import type { SystemSettingsRead, SystemSettingsUpdate } from "@/api/types/settings";
import { PopupMultiSelect } from "@/components/composes/PopupMultiSelect";
import AccessCard from "@/components/AccessCard";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useTheme } from "@/hooks/use-theme";
import { changeAppLanguage } from "@/i18n";
import { useUserStore } from "@/store/useUserStore";

export default function SettingsPage() {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();
  const userInfo = useUserStore((state) => state.userInfo);

  const [providers, setProviders] = useState<ModelProviderRead[]>([]);
  const [promptTemplateCount, setPromptTemplateCount] = useState<number | null>(null);
  const [form, setForm] = useState<SystemSettingsRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isCleaning, setIsCleaning] = useState(false);

  const canManage = Boolean(userInfo?.can_manage_system);
  const currentLanguage = i18n.resolvedLanguage === "en" ? "en" : "zh";
  const allModels = useMemo(
    () => providers.flatMap((provider) => provider.available_models.map((model) => ({ ...model, provider }))),
    [providers],
  );
  const modelWhitelistOptions = useMemo(
    () =>
      allModels.map((model) => ({
        value: String(model.id),
        label: model.model_name,
        description: model.provider.name,
        keywords: [String(model.id), model.provider.name],
      })),
    [allModels],
  );

  useEffect(() => {
    if (!canManage) {
      return;
    }

    async function loadData() {
      setIsLoading(true);
      try {
        const [providerResponse, promptTemplates, settings] = await Promise.all([
          listModelProviders(1, 100),
          listPromptTemplates().catch(() => []),
          getSystemSettings(),
        ]);
        setProviders(providerResponse.items);
        setPromptTemplateCount(promptTemplates.length);
        setForm(settings);
      } finally {
        setIsLoading(false);
      }
    }

    void loadData();
  }, [canManage]);

  async function runArtifactCleanup() {
    setIsCleaning(true);
    try {
      const result = await cleanupExpiredArtifacts();
      toast.success(t("settings.cleanupQueued", { status: result.status }));
    } catch (error) {
      showErrorToast(error, t("settings.cleanupQueueFailed"));
    } finally {
      setIsCleaning(false);
    }
  }

  async function saveSettings() {
    if (!form) {
      return;
    }
    setIsSaving(true);
    try {
      const payload: SystemSettingsUpdate = {
        allow_registration: form.allow_registration,
        max_chat_turns: form.max_chat_turns,
        allowed_model_ids: form.allowed_model_ids,
        default_max_context_messages: form.default_max_context_messages,
        default_auto_compaction_enabled: form.default_auto_compaction_enabled,
        private_chat_debounce_seconds: form.private_chat_debounce_seconds,
        rollback_retention_days: form.rollback_retention_days,
        rollback_cleanup_interval_hours: form.rollback_cleanup_interval_hours,
      };
      const updated = await updateSystemSettings(payload);
      setForm(updated);
      toast.success(t("settings.saved"));
    } catch (error) {
      showErrorToast(error, t("settings.saveFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  if (!canManage) {
    return <AccessCard description={t("settings.noPermission")} />;
  }

  return (
    <PageFrame title={t("settings.title")} description={t("settings.description")}>
      {isLoading || !form ? (
        <Card className="h-64 animate-pulse bg-muted/40" />
      ) : (
        <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>{t("settings.systemConfigTitle")}</CardTitle>
                <CardDescription>{t("settings.systemConfigDescription")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <label className="flex items-center gap-3 rounded-xl border border-border/70 px-4 py-4 text-sm">
                  <Checkbox
                    checked={form.allow_registration}
                    onCheckedChange={(checked) =>
                      setForm((prev) => (prev ? { ...prev, allow_registration: Boolean(checked) } : prev))
                    }
                  />
                  <div>
                    <div className="font-medium">{t("settings.allowRegistration")}</div>
                    <div className="text-muted-foreground">{t("settings.allowRegistrationHint")}</div>
                  </div>
                </label>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="grid gap-2">
                    <Label>{t("settings.maxChatTurns")}</Label>
                    <Input
                      type="number"
                      min={0}
                      value={String(form.max_chat_turns)}
                      onChange={(event) =>
                        setForm((prev) =>
                          prev ? { ...prev, max_chat_turns: Number(event.target.value || 0) } : prev,
                        )
                      }
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>{t("settings.privateChatDebounceSeconds")}</Label>
                    <Input
                      type="number"
                      min={0}
                      value={String(form.private_chat_debounce_seconds)}
                      onChange={(event) =>
                        setForm((prev) =>
                          prev
                            ? { ...prev, private_chat_debounce_seconds: Number(event.target.value || 0) }
                            : prev
                        )
                      }
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>{t("settings.defaultMaxContextMessages")}</Label>
                    <Input
                      type="number"
                      min={1}
                      value={String(form.default_max_context_messages)}
                      onChange={(event) =>
                        setForm((prev) =>
                          prev
                            ? { ...prev, default_max_context_messages: Number(event.target.value || 1) }
                            : prev
                        )
                      }
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>{t("settings.rollbackRetentionDays")}</Label>
                    <Input
                      type="number"
                      min={0}
                      value={String(form.rollback_retention_days)}
                      onChange={(event) =>
                        setForm((prev) =>
                          prev
                            ? { ...prev, rollback_retention_days: Number(event.target.value || 0) }
                            : prev
                        )
                      }
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>{t("settings.rollbackCleanupIntervalHours")}</Label>
                    <Input
                      type="number"
                      min={1}
                      value={String(form.rollback_cleanup_interval_hours)}
                      onChange={(event) =>
                        setForm((prev) =>
                          prev
                            ? { ...prev, rollback_cleanup_interval_hours: Number(event.target.value || 1) }
                            : prev
                        )
                      }
                    />
                  </div>
                </div>

                <label className="flex items-center gap-3 rounded-xl border border-border/70 px-4 py-4 text-sm">
                  <Checkbox
                    checked={form.default_auto_compaction_enabled}
                    onCheckedChange={(checked) =>
                      setForm((prev) =>
                        prev ? { ...prev, default_auto_compaction_enabled: Boolean(checked) } : prev
                      )
                    }
                  />
                  <div>
                    <div className="font-medium">{t("settings.defaultAutoCompaction")}</div>
                    <div className="text-muted-foreground">{t("settings.defaultAutoCompactionHint")}</div>
                  </div>
                </label>

                <div className="space-y-3">
                  <div>
                    <div className="font-medium">{t("settings.modelWhitelistTitle")}</div>
                    <div className="text-sm text-muted-foreground">{t("settings.modelWhitelistDescription")}</div>
                  </div>
                  {allModels.length ? (
                    <PopupMultiSelect
                      title={t("settings.modelWhitelistTitle")}
                      description={t("settings.modelWhitelistDescription")}
                      placeholder={t("settings.modelWhitelistTitle")}
                      searchPlaceholder={t("common.search")}
                      emptyText={t("settings.noModelsAvailable")}
                      value={form.allowed_model_ids.map((item) => String(item))}
                      onValueChange={(value) =>
                        setForm((prev) => (prev ? { ...prev, allowed_model_ids: value.map((item) => Number(item)) } : prev))
                      }
                      options={modelWhitelistOptions}
                    />
                  ) : (
                    <div className="rounded-xl border border-dashed border-border/70 px-4 py-4 text-sm text-muted-foreground">
                      {t("settings.noModelsAvailable")}
                    </div>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <Button onClick={saveSettings} disabled={isSaving}>
                    <Save className="mr-2 size-4" />
                    {isSaving ? t("common.saving") : t("settings.save")}
                  </Button>
                  <Badge variant="outline">
                    {t("settings.lastUpdated", { value: new Date(form.updated_at).toLocaleString() })}
                  </Badge>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t("settings.maintenanceTitle")}</CardTitle>
                <CardDescription>{t("settings.maintenanceQueueDescription")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Button variant="outline" disabled={isCleaning} onClick={runArtifactCleanup}>
                  <RefreshCcw className="mr-2 size-4" />
                  {isCleaning ? t("settings.queueing") : t("settings.queueExpiredArtifactCleanup")}
                </Button>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>{t("settings.backendCapabilityTitle")}</CardTitle>
                <CardDescription>{t("settings.backendCapabilityDescription")}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-border/70 p-4">
                  <div className="mb-2 text-sm text-muted-foreground">{t("settings.modelProvidersLabel")}</div>
                  <div className="text-2xl font-semibold">{providers.length}</div>
                </div>
                <div className="rounded-2xl border border-border/70 p-4">
                  <div className="mb-2 text-sm text-muted-foreground">{t("settings.registeredModelsLabel")}</div>
                  <div className="text-2xl font-semibold">{allModels.length}</div>
                </div>
                <div className="rounded-2xl border border-border/70 p-4">
                  <div className="mb-2 text-sm text-muted-foreground">{t("settings.promptTemplatesTitle")}</div>
                  <div className="text-2xl font-semibold">{promptTemplateCount ?? 0}</div>
                </div>
                <div className="rounded-2xl border border-border/70 p-4 text-sm text-muted-foreground">
                  <div className="mb-3">{t("settings.promptTemplatesDescription")}</div>
                  <Button asChild size="sm" variant="outline">
                    <Link to="/prompt-templates">{t("settings.openPromptTemplates")}</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MoonStar className="size-4 text-primary" />
                  {t("settings.preferencesTitle")}
                </CardTitle>
                <CardDescription>{t("settings.preferencesDescription")}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-2">
                  <Label className="flex items-center gap-2">
                    <Languages className="size-4 text-primary" />
                    {t("common.language")}
                  </Label>
                  <Select value={currentLanguage} onValueChange={(value) => void changeAppLanguage(value)}>
                    <SelectTrigger>
                      <SelectValue placeholder={t("common.language")} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="zh">{t("settings.languageZh")}</SelectItem>
                      <SelectItem value="en">{t("settings.languageEn")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>{t("common.theme")}</Label>
                  <Select value={theme} onValueChange={(value) => setTheme(value)}>
                    <SelectTrigger>
                      <SelectValue placeholder={t("common.theme")} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="light">{t("settings.themeLight")}</SelectItem>
                      <SelectItem value="dark">{t("settings.themeDark")}</SelectItem>
                      <SelectItem value="system">{t("settings.themeSystem")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="md:col-span-2">
                  <Badge variant="outline">{t("settings.localOnlyPreferences")}</Badge>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </PageFrame>
  );
}
