import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Plug, RefreshCcw, ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { clearWorkspacePluginError, listWorkspacePlugins, setWorkspacePluginEnabled, updateWorkspacePluginConfig, validateWorkspacePluginConfig } from "@/api/plugins";
import type { UserPluginRead } from "@/api/types/plugins";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { showErrorToast } from "@/api/client";

function formatJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

function parseJson(text: string): { value: Record<string, unknown> | null; errorKey: string | null } {
  try {
    const parsed = JSON.parse(text) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { value: null, errorKey: "jsonObjectRequired" };
    }
    return { value: parsed as Record<string, unknown>, errorKey: null };
  } catch {
    return { value: null, errorKey: "jsonInvalid" };
  }
}

export default function PluginsPage() {
  const { t } = useTranslation(["plugins", "common"]);
  const [plugins, setPlugins] = useState<UserPluginRead[]>([]);
  const [selectedPluginId, setSelectedPluginId] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isClearingError, setIsClearingError] = useState(false);
  const [configDraft, setConfigDraft] = useState("{}");
  const [configDraftError, setConfigDraftError] = useState<string | null>(null);

  const selectedPlugin = useMemo(
    () => plugins.find((item) => item.id === selectedPluginId) ?? null,
    [plugins, selectedPluginId],
  );

  useEffect(() => {
    void loadPlugins();
  }, []);

  useEffect(() => {
    if (!selectedPlugin) {
      setConfigDraft("{}");
      setConfigDraftError(null);
      return;
    }
    setConfigDraft(formatJson(selectedPlugin.user_config_json));
    setConfigDraftError(null);
  }, [selectedPlugin]);

  async function loadPlugins() {
    setIsLoading(true);
    try {
      const items = await listWorkspacePlugins();
      setPlugins(items);
      setSelectedPluginId((prev) => {
        if (prev && items.some((item) => item.id === prev)) {
          return prev;
        }
        return items[0]?.id || "";
      });
    } catch (error) {
      showErrorToast(error, t("plugins:loadFailed"));
    } finally {
      setIsLoading(false);
    }
  }

  function patchPlugin(next: UserPluginRead) {
    setPlugins((prev) => prev.map((item) => (item.id === next.id ? next : item)));
  }

  async function handleToggleEnabled(nextEnabled: boolean) {
    if (!selectedPlugin) {
      return;
    }
    setIsSaving(true);
    try {
      const updated = await setWorkspacePluginEnabled(selectedPlugin.id, nextEnabled);
      patchPlugin(updated);
      toast.success(t("plugins:toggleSuccess"));
    } catch (error) {
      showErrorToast(error, t("plugins:toggleFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSaveConfig() {
    if (!selectedPlugin) {
      return;
    }
    const parsed = parseJson(configDraft);
    if (!parsed.value) {
      setConfigDraftError(t(`plugins:${parsed.errorKey || "jsonInvalid"}`));
      return;
    }
    setConfigDraftError(null);
    setIsSaving(true);
    try {
      const updated = await updateWorkspacePluginConfig(selectedPlugin.id, parsed.value);
      patchPlugin(updated);
      toast.success(t("plugins:saveUserConfigSuccess"));
    } catch (error) {
      showErrorToast(error, t("plugins:saveUserConfigFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleValidateConfig() {
    if (!selectedPlugin) {
      return;
    }
    setIsValidating(true);
    try {
      const updated = await validateWorkspacePluginConfig(selectedPlugin.id);
      patchPlugin(updated);
      if (updated.user_error_text) {
        toast.error(updated.user_error_text);
      } else {
        toast.success(t("plugins:validateSuccess"));
      }
    } catch (error) {
      showErrorToast(error, t("plugins:validateFailed"));
    } finally {
      setIsValidating(false);
    }
  }

  async function handleClearError() {
    if (!selectedPlugin) {
      return;
    }
    setIsClearingError(true);
    try {
      const updated = await clearWorkspacePluginError(selectedPlugin.id);
      patchPlugin(updated);
      toast.success(t("plugins:clearErrorSuccess"));
    } catch (error) {
      showErrorToast(error, t("plugins:clearErrorFailed"));
    } finally {
      setIsClearingError(false);
    }
  }

  function resetUserConfig() {
    if (!selectedPlugin) {
      return;
    }
    setConfigDraft(formatJson(selectedPlugin.user_default_config_json));
    setConfigDraftError(null);
  }

  return (
    <PageFrame
      title={t("plugins:userTitle")}
      description={t("plugins:userDescription")}
      actions={
        <Button variant="outline" onClick={() => void loadPlugins()}>
          <RefreshCcw className="mr-2 size-4" />
          {t("plugins:refreshList")}
        </Button>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <Card className="border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Plug className="size-4 text-primary" />
              {t("plugins:pluginList")}
            </CardTitle>
            <CardDescription>{t("plugins:userPluginListDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading ? (
              <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
                {t("common:loading")}
              </div>
            ) : plugins.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
                {t("plugins:empty")}
              </div>
            ) : (
              plugins.map((plugin) => (
                <button
                  key={plugin.id}
                  type="button"
                  onClick={() => setSelectedPluginId(plugin.id)}
                  className={`w-full rounded-2xl border p-4 text-left transition ${selectedPluginId === plugin.id ? "border-primary bg-primary/5" : "border-border/70 hover:border-primary/40 hover:bg-accent/40"}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-medium">{plugin.display_name || plugin.name}</div>
                    <Badge variant={plugin.is_enabled ? "secondary" : "outline"}>
                      {plugin.is_enabled ? t("plugins:enabled") : t("plugins:disabled")}
                    </Badge>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge variant="outline">{plugin.plugin_type}</Badge>
                    <Badge variant="outline">{plugin.status}</Badge>
                    {plugin.user_error_text ? (
                      <Badge variant="destructive">{t("plugins:hasError")}</Badge>
                    ) : (
                      <Badge variant="secondary">{t("plugins:healthy")}</Badge>
                    )}
                  </div>
                </button>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle className="text-base">
              {selectedPlugin?.display_name || t("plugins:selectedPlugin")}
            </CardTitle>
            <CardDescription>
              {selectedPlugin ? selectedPlugin.name : t("plugins:selectPrompt")}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {!selectedPlugin ? (
              <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
                {t("plugins:selectPrompt")}
              </div>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-2 rounded-lg border border-border/70 px-3 py-2 text-sm">
                    <Switch
                      checked={selectedPlugin.is_enabled}
                      disabled={isSaving}
                      onCheckedChange={(checked) => void handleToggleEnabled(checked)}
                    />
                    <span>{t("plugins:enabledForMe")}</span>
                  </div>
                  <Badge variant="outline">{selectedPlugin.plugin_type}</Badge>
                  <Badge variant="outline">{selectedPlugin.status}</Badge>
                </div>

                {selectedPlugin.user_error_text ? (
                  <div className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm">
                    <div className="mb-2 flex items-center gap-2 font-medium text-destructive">
                      <ShieldAlert className="size-4" />
                      {t("plugins:userErrorTitle")}
                    </div>
                    <div className="whitespace-pre-wrap break-words text-foreground/90">
                      {selectedPlugin.user_error_text}
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      {t("plugins:errorUpdatedAt", { value: formatTime(selectedPlugin.user_error_at) })}
                    </div>
                    <div className="mt-3">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={isClearingError}
                        onClick={() => void handleClearError()}
                      >
                        {isClearingError ? t("common:saving") : t("plugins:clearUserError")}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-xl border border-border/70 bg-muted/20 p-4 text-sm">
                    <div className="flex items-center gap-2 font-medium">
                      <CheckCircle2 className="size-4 text-primary" />
                      {t("plugins:noUserError")}
                    </div>
                  </div>
                )}

                <div className="space-y-2">
                  <Label>{t("plugins:userConfigLabel")}</Label>
                  <Textarea
                    rows={12}
                    value={configDraft}
                    onChange={(event) => {
                      setConfigDraft(event.target.value);
                      if (configDraftError) {
                        setConfigDraftError(null);
                      }
                    }}
                  />
                  {configDraftError ? (
                    <div className="text-sm text-destructive">{configDraftError}</div>
                  ) : null}
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button disabled={isSaving} onClick={() => void handleSaveConfig()}>
                    {isSaving ? t("common:saving") : t("plugins:saveUserConfig")}
                  </Button>
                  <Button variant="outline" disabled={isValidating} onClick={() => void handleValidateConfig()}>
                    {isValidating ? t("common:saving") : t("plugins:validateUserConfig")}
                  </Button>
                  <Button variant="outline" onClick={resetUserConfig}>
                    {t("plugins:resetUserConfig")}
                  </Button>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>{t("plugins:userConfigSchema")}</Label>
                    <Textarea rows={8} value={formatJson(selectedPlugin.user_config_schema_json)} readOnly />
                  </div>
                  <div className="space-y-2">
                    <Label>{t("plugins:adminConfigReadOnly")}</Label>
                    <Textarea rows={8} value={formatJson(selectedPlugin.default_config_json)} readOnly />
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </PageFrame>
  );
}
