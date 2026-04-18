import { useEffect, useMemo, useState } from "react";
import { Languages, MoonStar, Save } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { changeAppLanguage } from "@/i18n";
import { listModelProviders } from "@/api/providers";
import { getSystemSettings, triggerRollbackCleanup, updateSystemSettings } from "@/api/settings";
import type { SystemSettingsUpdate } from "@/api/types";
import AccessCard from "@/components/AccessCard";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useUserStore } from "@/store/useUserStore";
import { useTheme } from "@/hooks/use-theme";

export default function SettingsPage() {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();
  const userInfo = useUserStore((state) => state.userInfo);
  const [form, setForm] = useState<SystemSettingsUpdate | null>(null);
  const [models, setModels] = useState<{ id: number; label: string }[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const canManage = Boolean(userInfo?.can_manage_system);
  const currentLanguage = i18n.resolvedLanguage === "en" ? "en" : "zh";

  async function fetchData() {
    setIsLoading(true);
    try {
      const [settings, providers] = await Promise.all([getSystemSettings(), listModelProviders(1, 100)]);
      setForm({
        allow_registration: settings.allow_registration,
        max_chat_turns: settings.max_chat_turns,
        allowed_model_ids: settings.allowed_model_ids,
        default_max_context_tokens: settings.default_max_context_tokens,
        default_max_rounds: settings.default_max_rounds,
        default_compact_memory_max_items: settings.default_compact_memory_max_items,
        default_auto_compaction_trigger_rounds: settings.default_auto_compaction_trigger_rounds,
        default_auto_compaction_message_count: settings.default_auto_compaction_message_count,
        default_auto_compaction_memory_max_items: settings.default_auto_compaction_memory_max_items,
        default_manual_compaction_message_count: settings.default_manual_compaction_message_count,
        default_manual_compaction_memory_max_items: settings.default_manual_compaction_memory_max_items,
        default_manual_compaction_mode: settings.default_manual_compaction_mode,
        dispatch_thread_pool_max_workers: settings.dispatch_thread_pool_max_workers,
        llm_max_concurrency: settings.llm_max_concurrency,
        embedding_max_concurrency: settings.embedding_max_concurrency,
        private_chat_debounce_ms: settings.private_chat_debounce_ms,
        group_chat_debounce_ms: settings.group_chat_debounce_ms,
        typing_debounce_max_extra_ms: settings.typing_debounce_max_extra_ms,
        idle_followup_medium_turn_threshold: settings.idle_followup_medium_turn_threshold,
        idle_followup_high_turn_threshold: settings.idle_followup_high_turn_threshold,
        idle_followup_low_activity_seconds: settings.idle_followup_low_activity_seconds,
        idle_followup_medium_activity_seconds: settings.idle_followup_medium_activity_seconds,
        idle_followup_high_activity_seconds: settings.idle_followup_high_activity_seconds,
        rollback_retention_days: settings.rollback_retention_days,
        rollback_cleanup_interval_hours: settings.rollback_cleanup_interval_hours,
      });
      setModels(
        providers.items.flatMap((provider) =>
          provider.available_models.map((model) => ({ id: model.id, label: `${provider.name} / ${model.model_name}` })),
        ),
      );
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (canManage) void fetchData();
  }, [canManage]);

  const selectedModels = useMemo(() => new Set(form?.allowed_model_ids || []), [form]);

  function toggleModel(modelId: number, checked: boolean) {
    setForm((prev) => {
      if (!prev) return prev;
      const next = new Set(prev.allowed_model_ids || []);
      if (checked) next.add(modelId);
      else next.delete(modelId);
      return { ...prev, allowed_model_ids: Array.from(next) };
    });
  }

  async function saveSettings() {
    if (!form) return;
    setIsSaving(true);
    try {
      const saved = await updateSystemSettings({ ...form, allowed_model_ids: form.allowed_model_ids || [] });
      setForm({
        allow_registration: saved.allow_registration,
        max_chat_turns: saved.max_chat_turns,
        allowed_model_ids: saved.allowed_model_ids,
        default_max_context_tokens: saved.default_max_context_tokens,
        default_max_rounds: saved.default_max_rounds,
        default_compact_memory_max_items: saved.default_compact_memory_max_items,
        default_auto_compaction_trigger_rounds: saved.default_auto_compaction_trigger_rounds,
        default_auto_compaction_message_count: saved.default_auto_compaction_message_count,
        default_auto_compaction_memory_max_items: saved.default_auto_compaction_memory_max_items,
        default_manual_compaction_message_count: saved.default_manual_compaction_message_count,
        default_manual_compaction_memory_max_items: saved.default_manual_compaction_memory_max_items,
        default_manual_compaction_mode: saved.default_manual_compaction_mode,
        dispatch_thread_pool_max_workers: saved.dispatch_thread_pool_max_workers,
        llm_max_concurrency: saved.llm_max_concurrency,
        embedding_max_concurrency: saved.embedding_max_concurrency,
        private_chat_debounce_ms: saved.private_chat_debounce_ms,
        group_chat_debounce_ms: saved.group_chat_debounce_ms,
        typing_debounce_max_extra_ms: saved.typing_debounce_max_extra_ms,
        idle_followup_medium_turn_threshold: saved.idle_followup_medium_turn_threshold,
        idle_followup_high_turn_threshold: saved.idle_followup_high_turn_threshold,
        idle_followup_low_activity_seconds: saved.idle_followup_low_activity_seconds,
        idle_followup_medium_activity_seconds: saved.idle_followup_medium_activity_seconds,
        idle_followup_high_activity_seconds: saved.idle_followup_high_activity_seconds,
        rollback_retention_days: saved.rollback_retention_days,
        rollback_cleanup_interval_hours: saved.rollback_cleanup_interval_hours,
      });
      toast.success(t("settings.saved"));
    } finally {
      setIsSaving(false);
    }
  }

  async function runRollbackCleanup() {
    try {
      const result = await triggerRollbackCleanup();
      toast.success(`rollback cleanup: ${result.cocoons ?? 0} cocoons, ${result.messages ?? 0} messages`);
    } catch {
      toast.error("Failed to run rollback cleanup");
    }
  }

  if (!canManage) {
    return <AccessCard description={t("settings.noPermission")} />;
  }

  return (
    <PageFrame
      title={t("settings.title")}
      description={t("settings.description")}
      actions={
        <Button disabled={!form || isSaving} onClick={saveSettings}>
          <Save className="mr-2 size-4" />
          {isSaving ? t("common.saving") : t("settings.save")}
        </Button>
      }
    >
      {isLoading || !form ? (
        <Card className="h-64 animate-pulse bg-muted/40" />
      ) : (
        <div className="grid gap-6 xl:grid-cols-[1fr_1.2fr]">
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>{t("settings.coreTitle")}</CardTitle>
                <CardDescription>{t("settings.coreDescription")}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4">
                <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
                  <Checkbox checked={Boolean(form.allow_registration)} onCheckedChange={(checked) => setForm((prev) => (prev ? { ...prev, allow_registration: Boolean(checked) } : prev))} />
                  <span>{t("settings.allowRegistration")}</span>
                </label>
                <div className="grid gap-2">
                  <Label>{t("settings.maxChatTurns")}</Label>
                  <Input type="number" value={form.max_chat_turns ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, max_chat_turns: Number(event.target.value) } : prev))} />
                </div>
                <div className="grid gap-2">
                  <Label>{t("settings.defaultMaxContext")}</Label>
                  <Input type="number" value={form.default_max_context_tokens ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, default_max_context_tokens: Number(event.target.value) } : prev))} />
                </div>
                <div className="grid gap-2">
                  <Label>{t("settings.defaultMaxRounds")}</Label>
                  <Input type="number" value={form.default_max_rounds ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, default_max_rounds: Number(event.target.value) } : prev))} />
                </div>
                <div className="grid gap-2">
                  <Label>{t("settings.defaultCompactMemory")}</Label>
                  <Input type="number" value={form.default_compact_memory_max_items ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, default_compact_memory_max_items: Number(event.target.value) } : prev))} />
                  <p className="text-xs text-muted-foreground">{t("settings.compactMemoryHelp")}</p>
                </div>
                <div className="grid gap-2 md:grid-cols-2">
                  <div className="grid gap-2">
                    <Label>Auto compaction trigger rounds</Label>
                    <Input type="number" value={form.default_auto_compaction_trigger_rounds ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, default_auto_compaction_trigger_rounds: Number(event.target.value) } : prev))} />
                  </div>
                  <div className="grid gap-2">
                    <Label>Auto compaction message count</Label>
                    <Input type="number" value={form.default_auto_compaction_message_count ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, default_auto_compaction_message_count: Number(event.target.value) } : prev))} />
                  </div>
                </div>
                <div className="grid gap-2 md:grid-cols-3">
                  <div className="grid gap-2">
                    <Label>Auto compaction max memories</Label>
                    <Input type="number" value={form.default_auto_compaction_memory_max_items ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, default_auto_compaction_memory_max_items: Number(event.target.value) } : prev))} />
                  </div>
                  <div className="grid gap-2">
                    <Label>Manual compaction message count</Label>
                    <Input type="number" value={form.default_manual_compaction_message_count ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, default_manual_compaction_message_count: Number(event.target.value) } : prev))} />
                  </div>
                  <div className="grid gap-2">
                    <Label>Manual compaction max memories</Label>
                    <Input type="number" value={form.default_manual_compaction_memory_max_items ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, default_manual_compaction_memory_max_items: Number(event.target.value) } : prev))} />
                  </div>
                </div>
                <div className="grid gap-2">
                  <Label>Manual compaction mode</Label>
                  <Select value={form.default_manual_compaction_mode ?? "all"} onValueChange={(value) => setForm((prev) => (prev ? { ...prev, default_manual_compaction_mode: value } : prev))}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select compaction mode" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Compress all remaining context</SelectItem>
                      <SelectItem value="earliest">Compress only the earliest configured messages</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2 md:grid-cols-3">
                  <div className="grid gap-2">
                    <Label>Dispatch thread pool</Label>
                    <Input type="number" value={form.dispatch_thread_pool_max_workers ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, dispatch_thread_pool_max_workers: Number(event.target.value) } : prev))} />
                  </div>
                  <div className="grid gap-2">
                    <Label>LLM max concurrency</Label>
                    <Input type="number" value={form.llm_max_concurrency ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, llm_max_concurrency: Number(event.target.value) } : prev))} />
                  </div>
                  <div className="grid gap-2">
                    <Label>Embedding max concurrency</Label>
                    <Input type="number" value={form.embedding_max_concurrency ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, embedding_max_concurrency: Number(event.target.value) } : prev))} />
                  </div>
                </div>
                <div className="grid gap-2 md:grid-cols-3">
                  <div className="grid gap-2">
                    <Label>Private debounce ms</Label>
                    <Input type="number" value={form.private_chat_debounce_ms ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, private_chat_debounce_ms: Number(event.target.value) } : prev))} />
                  </div>
                  <div className="grid gap-2">
                    <Label>Group debounce ms</Label>
                    <Input type="number" value={form.group_chat_debounce_ms ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, group_chat_debounce_ms: Number(event.target.value) } : prev))} />
                  </div>
                  <div className="grid gap-2">
                    <Label>Typing extra debounce ms</Label>
                    <Input type="number" value={form.typing_debounce_max_extra_ms ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, typing_debounce_max_extra_ms: Number(event.target.value) } : prev))} />
                  </div>
                </div>
                <div className="grid gap-2 md:grid-cols-2">
                  <div className="grid gap-2">
                    <Label>Idle medium turn threshold</Label>
                    <Input type="number" value={form.idle_followup_medium_turn_threshold ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, idle_followup_medium_turn_threshold: Number(event.target.value) } : prev))} />
                  </div>
                  <div className="grid gap-2">
                    <Label>Idle high turn threshold</Label>
                    <Input type="number" value={form.idle_followup_high_turn_threshold ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, idle_followup_high_turn_threshold: Number(event.target.value) } : prev))} />
                  </div>
                </div>
                <div className="grid gap-2 md:grid-cols-3">
                  <div className="grid gap-2">
                    <Label>Idle low activity seconds</Label>
                    <Input type="number" value={form.idle_followup_low_activity_seconds ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, idle_followup_low_activity_seconds: Number(event.target.value) } : prev))} />
                  </div>
                  <div className="grid gap-2">
                    <Label>Idle medium activity seconds</Label>
                    <Input type="number" value={form.idle_followup_medium_activity_seconds ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, idle_followup_medium_activity_seconds: Number(event.target.value) } : prev))} />
                  </div>
                  <div className="grid gap-2">
                    <Label>Idle high activity seconds</Label>
                    <Input type="number" value={form.idle_followup_high_activity_seconds ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, idle_followup_high_activity_seconds: Number(event.target.value) } : prev))} />
                  </div>
                </div>
                <div className="grid gap-2">
                  <Label>{t("settings.rollbackRetentionDays")}</Label>
                  <Input type="number" value={form.rollback_retention_days ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, rollback_retention_days: Number(event.target.value) } : prev))} />
                </div>
                <div className="grid gap-2">
                  <Label>{t("settings.rollbackCleanupIntervalHours")}</Label>
                  <Input type="number" value={form.rollback_cleanup_interval_hours ?? 0} onChange={(event) => setForm((prev) => (prev ? { ...prev, rollback_cleanup_interval_hours: Number(event.target.value) } : prev))} />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Languages className="size-4 text-primary" />{t("settings.preferencesTitle")}</CardTitle>
                <CardDescription>{t("settings.preferencesDescription")}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-2">
                  <Label>{t("common.language")}</Label>
                  <Select value={currentLanguage} onValueChange={(value) => void changeAppLanguage(value)}>
                    <SelectTrigger>
                      <SelectValue placeholder={t("common.language")} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="zh">{t("settings.languageZh")}</SelectItem>
                      <SelectItem value="en">{t("settings.languageEn")}</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">{t("settings.languageDescription")}</p>
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
                  <p className="text-xs text-muted-foreground">{t("settings.themeDescription")}</p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t("settings.maintenanceTitle")}</CardTitle>
                <CardDescription>{t("settings.maintenanceDescription")}</CardDescription>
              </CardHeader>
              <CardContent>
                <Button variant="outline" onClick={runRollbackCleanup}>{t("settings.runRollbackCleanup")}</Button>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><MoonStar className="size-4 text-primary" />{t("settings.modelWhitelistTitle")}</CardTitle>
              <CardDescription>{t("settings.modelWhitelistDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-2">
                {form.allowed_model_ids?.length ? (
                  form.allowed_model_ids.map((id) => (
                    <Badge key={id} variant="outline">模型 #{id}</Badge>
                  ))
                ) : (
                  <Badge variant="secondary">{t("settings.unrestrictedModels")}</Badge>
                )}
              </div>
              <div className="grid gap-2">
                {models.map((model) => (
                  <label key={model.id} className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
                    <Checkbox checked={selectedModels.has(model.id)} onCheckedChange={(checked) => toggleModel(model.id, Boolean(checked))} />
                    <span>{model.label}</span>
                  </label>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </PageFrame>
  );
}
