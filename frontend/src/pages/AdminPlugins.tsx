import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Eye, EyeOff, Plug, RefreshCcw, Settings2, ShieldAlert, Upload, Zap } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import {
  deleteAdminPlugin,
  getAdminPlugin,
  installAdminPlugin,
  listAdminPluginGroupVisibility,
  listAdminPluginSharedPackages,
  listAdminPlugins,
  setAdminPluginEnabled,
  setAdminPluginEventEnabled,
  setAdminPluginGlobalVisibility,
  setAdminPluginGroupVisibility,
  runAdminPluginEventNow,
  updateAdminPlugin,
  updateAdminPluginConfig,
  validateAdminPluginConfig,
  updateAdminPluginEventConfig,
} from "@/api/admin-plugins";
import { showErrorToast } from "@/api/client";
import { listGroups } from "@/api/groups";
import { resolveActualId } from "@/api/id-map";
import type { GroupRead } from "@/api/types";
import type { AdminPluginDetailRead, AdminPluginListItemRead, AdminPluginSharedPackageRead, PluginGroupVisibilityRead } from "@/api/types/plugins";
import AccessCard from "@/components/AccessCard";
import { PopupSelect } from "@/components/composes/PopupSelect";
import PageFrame from "@/components/PageFrame";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { hasAnyPermission } from "@/lib/permissions";
import { useUserStore } from "@/store/useUserStore";

function formatJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function parseObjectJson(text: string): { value: Record<string, unknown> | null; error: string | null } {
  try {
    const parsed = JSON.parse(text) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { value: null, error: "jsonObjectRequired" };
    }
    return { value: parsed as Record<string, unknown>, error: null };
  } catch {
    return { value: null, error: "jsonInvalid" };
  }
}

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

export default function AdminPluginsPage() {
  const { t } = useTranslation(["plugins", "common"]);
  const userInfo = useUserStore((state) => state.userInfo);
  const canView = hasAnyPermission(userInfo, ["plugins:read", "plugins:write", "plugins:run"]);
  const canWrite = hasAnyPermission(userInfo, ["plugins:write"]);
  const canRun = hasAnyPermission(userInfo, ["plugins:run"]);

  const installInputRef = useRef<HTMLInputElement | null>(null);
  const updateInputRef = useRef<HTMLInputElement | null>(null);
  const runtimeMonitorTokenRef = useRef(0);
  const runtimeToastKeyRef = useRef("");

  const [plugins, setPlugins] = useState<AdminPluginListItemRead[]>([]);
  const [selectedPluginId, setSelectedPluginId] = useState("");
  const [selectedPlugin, setSelectedPlugin] = useState<AdminPluginDetailRead | null>(null);
  const [groupVisibility, setGroupVisibility] = useState<PluginGroupVisibilityRead[]>([]);
  const [groups, setGroups] = useState<GroupRead[]>([]);
  const [sharedPackages, setSharedPackages] = useState<AdminPluginSharedPackageRead[]>([]);

  const [globalConfigDraft, setGlobalConfigDraft] = useState("{}");
  const [globalConfigErrorKey, setGlobalConfigErrorKey] = useState<string | null>(null);
  const [eventConfigDrafts, setEventConfigDrafts] = useState<Record<string, string>>({});
  const [eventConfigErrorKeys, setEventConfigErrorKeys] = useState<Record<string, string | null>>({});

  const [selectedGroupId, setSelectedGroupId] = useState("");
  const [newGroupVisibility, setNewGroupVisibility] = useState(true);

  const [isListLoading, setIsListLoading] = useState(true);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const [isValidatingGlobalConfig, setIsValidatingGlobalConfig] = useState(false);
  const [runningEventName, setRunningEventName] = useState<string | null>(null);
  const [isInstalling, setIsInstalling] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isGroupSaving, setIsGroupSaving] = useState(false);
  const [isSharedLibsOpen, setIsSharedLibsOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const groupNameByActualId = useMemo(() => {
    return new Map(groups.map((group) => [resolveActualId("group", group.gid), group.name] as const));
  }, [groups]);
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

  useEffect(() => {
    if (!canView) {
      return;
    }
    void loadPluginList();
    void loadAuxiliaryData();
  }, [canView]);

  useEffect(() => {
    if (!selectedPluginId || !canView) {
      runtimeMonitorTokenRef.current += 1;
      runtimeToastKeyRef.current = "";
      setSelectedPlugin(null);
      setGroupVisibility([]);
      return;
    }
    void loadSelectedPlugin(selectedPluginId);
  }, [selectedPluginId, canView]);

  useEffect(() => {
    return () => {
      runtimeMonitorTokenRef.current += 1;
    };
  }, []);

  useEffect(() => {
    if (!selectedPlugin) {
      setGlobalConfigDraft("{}");
      setGlobalConfigErrorKey(null);
      setEventConfigDrafts({});
      setEventConfigErrorKeys({});
      return;
    }
    setGlobalConfigDraft(formatJson(selectedPlugin.config_json));
    setGlobalConfigErrorKey(null);
    setEventConfigDrafts(
      Object.fromEntries(selectedPlugin.events.map((event) => [event.name, formatJson(event.config_json)])),
    );
    setEventConfigErrorKeys(
      Object.fromEntries(selectedPlugin.events.map((event) => [event.name, null])),
    );
  }, [selectedPlugin]);

  async function loadPluginList(preferredPluginId?: string) {
    setIsListLoading(true);
    try {
      const items = await listAdminPlugins();
      setPlugins(items);
      setSelectedPluginId((prev) => {
        if (preferredPluginId && items.some((item) => item.id === preferredPluginId)) {
          return preferredPluginId;
        }
        if (prev && items.some((item) => item.id === prev)) {
          return prev;
        }
        return items[0]?.id || "";
      });
    } catch (error) {
      showErrorToast(error, t("plugins:loadFailed"));
    } finally {
      setIsListLoading(false);
    }
  }

  async function loadSelectedPlugin(pluginId: string) {
    setIsDetailLoading(true);
    try {
      const [plugin, visibilityRows] = await Promise.all([
        getAdminPlugin(pluginId),
        listAdminPluginGroupVisibility(pluginId),
      ]);
      setSelectedPlugin(plugin);
      setGroupVisibility(visibilityRows);
      if (!selectedGroupId && groups.length > 0) {
        setSelectedGroupId(groups[0].gid);
      }
    } catch (error) {
      showErrorToast(error, t("plugins:detailLoadFailed"));
    } finally {
      setIsDetailLoading(false);
    }
  }

  async function loadAuxiliaryData() {
    try {
      const [packages, groupResponse] = await Promise.all([
        listAdminPluginSharedPackages(),
        listGroups(1, 200).catch(() => null),
      ]);
      setSharedPackages(packages);
      if (groupResponse) {
        setGroups(groupResponse.items);
        if (!selectedGroupId) {
          setSelectedGroupId(groupResponse.items[0]?.gid || "");
        }
      }
    } catch (error) {
      showErrorToast(error, t("plugins:auxLoadFailed"));
    }
  }

  function syncSelectedPlugin(next: AdminPluginDetailRead) {
    setSelectedPlugin(next);
    setSelectedPluginId(next.id);
    setPlugins((prev) => {
      const index = prev.findIndex((item) => item.id === next.id);
      if (index < 0) {
        return [...prev, next];
      }
      const cloned = [...prev];
      cloned[index] = next;
      return cloned;
    });
  }

  function describeRuntimeIssue(plugin: AdminPluginDetailRead) {
    const errorText = plugin.run_state?.error_text?.trim();
    if (errorText) {
      return errorText;
    }
    return `${t("plugins:runtimeStatus")}: ${plugin.run_state?.status || "-"}`;
  }

  async function monitorPluginRuntime(
    pluginId: string,
    options?: {
      attempts?: number;
      intervalMs?: number;
    },
  ) {
    const attempts = options?.attempts ?? 8;
    const intervalMs = options?.intervalMs ?? 1500;
    const monitorToken = ++runtimeMonitorTokenRef.current;
    let lastErrorText = selectedPlugin?.id === pluginId ? selectedPlugin.run_state?.error_text?.trim() || "" : "";

    for (let attempt = 0; attempt < attempts; attempt += 1) {
      await new Promise<void>((resolve) => {
        window.setTimeout(resolve, intervalMs);
      });
      if (monitorToken !== runtimeMonitorTokenRef.current) {
        return;
      }
      try {
        const detail = await getAdminPlugin(pluginId);
        if (monitorToken !== runtimeMonitorTokenRef.current) {
          return;
        }
        syncSelectedPlugin(detail);
        const errorText = detail.run_state?.error_text?.trim() || "";
        const hasFailed = detail.run_state?.status === "failed";
        if (errorText && errorText !== lastErrorText) {
          const toastKey = `${pluginId}:${errorText}`;
          if (runtimeToastKeyRef.current !== toastKey) {
            runtimeToastKeyRef.current = toastKey;
            toast.error(t("plugins:runtimeState"), { description: errorText });
          }
          return;
        }
        if (hasFailed) {
          const description = describeRuntimeIssue(detail);
          const toastKey = `${pluginId}:${description}`;
          if (runtimeToastKeyRef.current !== toastKey) {
            runtimeToastKeyRef.current = toastKey;
            toast.error(t("plugins:runtimeState"), { description });
          }
          return;
        }
        lastErrorText = errorText;
        if (detail.status !== "enabled") {
          return;
        }
      } catch {
        return;
      }
    }
  }

  async function handleInstallFromInput(file: File | null) {
    if (!file) {
      return;
    }
    setIsInstalling(true);
    try {
      const installed = await installAdminPlugin(file);
      syncSelectedPlugin(installed);
      toast.success(t("plugins:installSuccess"));
      await loadPluginList(installed.id);
    } catch (error) {
      showErrorToast(error, t("plugins:installFailed"));
    } finally {
      setIsInstalling(false);
    }
  }

  async function handleUpdateFromInput(file: File | null) {
    if (!selectedPlugin || !file) {
      return;
    }
    setIsUpdating(true);
    try {
      const updated = await updateAdminPlugin(selectedPlugin.id, file);
      syncSelectedPlugin(updated);
      toast.success(t("plugins:updateSuccess"));
      await loadPluginList(updated.id);
    } catch (error) {
      showErrorToast(error, t("plugins:updateFailed"));
    } finally {
      setIsUpdating(false);
    }
  }

  async function handleTogglePluginRuntime(enabled: boolean) {
    if (!selectedPlugin) {
      return;
    }
    try {
      const updated = await setAdminPluginEnabled(selectedPlugin.id, enabled);
      syncSelectedPlugin(updated);
      toast.success(t("plugins:toggleRuntimeSuccess"));
      if (enabled) {
        runtimeToastKeyRef.current = "";
        void monitorPluginRuntime(updated.id);
      } else {
        runtimeMonitorTokenRef.current += 1;
      }
    } catch (error) {
      showErrorToast(error, t("plugins:toggleRuntimeFailed"));
    }
  }

  async function handleDeletePlugin() {
    if (!selectedPlugin) {
      return;
    }
    setIsDeleting(true);
    try {
      await deleteAdminPlugin(selectedPlugin.id);
      toast.success(t("plugins:deleteSuccess"));
      setIsDeleteDialogOpen(false);
      setSelectedPlugin(null);
      setSelectedPluginId("");
      await loadPluginList();
    } catch (error) {
      showErrorToast(error, t("plugins:deleteFailed"));
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleSaveGlobalConfig() {
    if (!selectedPlugin) {
      return;
    }
    const parsed = parseObjectJson(globalConfigDraft);
    if (!parsed.value || parsed.error) {
      setGlobalConfigErrorKey(parsed.error || "jsonInvalid");
      return;
    }
    setGlobalConfigErrorKey(null);
    setIsSavingConfig(true);
    try {
      const updated = await updateAdminPluginConfig(selectedPlugin.id, parsed.value);
      syncSelectedPlugin(updated);
      toast.success(t("plugins:saveGlobalConfigSuccess"));
    } catch (error) {
      showErrorToast(error, t("plugins:saveGlobalConfigFailed"));
    } finally {
      setIsSavingConfig(false);
    }
  }

  async function handleValidateGlobalConfig() {
    if (!selectedPlugin) {
      return;
    }
    const parsed = parseObjectJson(globalConfigDraft);
    if (!parsed.value || parsed.error) {
      setGlobalConfigErrorKey(parsed.error || "jsonInvalid");
      return;
    }
    setGlobalConfigErrorKey(null);
    setIsValidatingGlobalConfig(true);
    try {
      const detail = await validateAdminPluginConfig(selectedPlugin.id, parsed.value);
      syncSelectedPlugin(detail);
      toast.success(t("plugins:validateSuccess"));
    } catch (error) {
      showErrorToast(error, t("plugins:validateFailed"));
    } finally {
      setIsValidatingGlobalConfig(false);
    }
  }

  async function handleSaveEventConfig(eventName: string) {
    if (!selectedPlugin) {
      return;
    }
    const draft = eventConfigDrafts[eventName];
    const parsed = parseObjectJson(draft || "{}");
    if (!parsed.value || parsed.error) {
      setEventConfigErrorKeys((prev) => ({ ...prev, [eventName]: parsed.error || "jsonInvalid" }));
      return;
    }
    setEventConfigErrorKeys((prev) => ({ ...prev, [eventName]: null }));
    setIsSavingConfig(true);
    try {
      const updated = await updateAdminPluginEventConfig(selectedPlugin.id, eventName, parsed.value);
      syncSelectedPlugin(updated);
      toast.success(t("plugins:saveEventConfigSuccess"));
    } catch (error) {
      showErrorToast(error, t("plugins:saveEventConfigFailed"));
    } finally {
      setIsSavingConfig(false);
    }
  }

  async function handleToggleEventEnabled(eventName: string, enabled: boolean) {
    if (!selectedPlugin) {
      return;
    }
    try {
      const updated = await setAdminPluginEventEnabled(selectedPlugin.id, eventName, enabled);
      syncSelectedPlugin(updated);
      toast.success(t("plugins:toggleEventSuccess"));
    } catch (error) {
      showErrorToast(error, t("plugins:toggleEventFailed"));
    }
  }

  async function handleRunEventNow(eventName: string) {
    if (!selectedPlugin) {
      return;
    }
    setRunningEventName(eventName);
    try {
      const updated = await runAdminPluginEventNow(selectedPlugin.id, eventName);
      syncSelectedPlugin(updated);
      toast.success(t("plugins:runEventNowSuccess"));
    } catch (error) {
      showErrorToast(error, t("plugins:runEventNowFailed"));
    } finally {
      setRunningEventName(null);
    }
  }

  async function handleSetGlobalVisibility(visible: boolean) {
    if (!selectedPlugin) {
      return;
    }
    try {
      const updated = await setAdminPluginGlobalVisibility(selectedPlugin.id, visible);
      syncSelectedPlugin(updated);
      toast.success(t("plugins:visibilitySuccess"));
    } catch (error) {
      showErrorToast(error, t("plugins:visibilityFailed"));
    }
  }

  async function handleSetGroupVisibility() {
    if (!selectedPlugin || !selectedGroupId) {
      return;
    }
    setIsGroupSaving(true);
    try {
      await setAdminPluginGroupVisibility(selectedPlugin.id, selectedGroupId, newGroupVisibility);
      const rows = await listAdminPluginGroupVisibility(selectedPlugin.id);
      setGroupVisibility(rows);
      toast.success(t("plugins:groupVisibilitySuccess"));
    } catch (error) {
      showErrorToast(error, t("plugins:groupVisibilityFailed"));
    } finally {
      setIsGroupSaving(false);
    }
  }

  if (!canView) {
    return <AccessCard description={t("plugins:noPermission")} />;
  }

  return (
    <PageFrame
      title={t("plugins:adminTitle")}
      description={t("plugins:adminDescription")}
      actions={
        <div className="flex flex-wrap gap-2">
          <input
            ref={installInputRef}
            type="file"
            accept=".zip,application/zip"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              void handleInstallFromInput(file);
              event.currentTarget.value = "";
            }}
          />
          <input
            ref={updateInputRef}
            type="file"
            accept=".zip,application/zip"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              void handleUpdateFromInput(file);
              event.currentTarget.value = "";
            }}
          />
          <Button
            disabled={!canWrite || isInstalling}
            onClick={() => installInputRef.current?.click()}
          >
            <Upload className="mr-2 size-4" />
            {isInstalling ? t("common:saving") : t("plugins:installPlugin")}
          </Button>
          <Button
            variant="outline"
            disabled={!selectedPlugin || !canWrite || isUpdating}
            onClick={() => updateInputRef.current?.click()}
          >
            <Upload className="mr-2 size-4" />
            {isUpdating ? t("common:saving") : t("plugins:updatePlugin")}
          </Button>
          <Button variant="outline" onClick={() => void loadPluginList(selectedPluginId)}>
            <RefreshCcw className="mr-2 size-4" />
            {t("plugins:refreshList")}
          </Button>
        </div>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
        <Card className="border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Plug className="size-4 text-primary" />
              {t("plugins:pluginList")}
            </CardTitle>
            <CardDescription>{t("plugins:adminPluginListDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isListLoading ? (
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
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium">{plugin.display_name || plugin.name}</div>
                    <Badge variant={plugin.status === "enabled" ? "secondary" : "outline"}>
                      {plugin.status}
                    </Badge>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge variant="outline">{plugin.plugin_type}</Badge>
                    <Badge variant="outline">{plugin.active_version_id || t("plugins:noVersion")}</Badge>
                    <Badge variant={plugin.is_globally_visible ? "secondary" : "outline"}>
                      {plugin.is_globally_visible ? t("plugins:visible") : t("plugins:hidden")}
                    </Badge>
                  </div>
                </button>
              ))
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="border-border/70 bg-card/90">
            <CardHeader>
              <CardTitle className="text-base">
                {selectedPlugin?.display_name || t("plugins:selectedPlugin")}
              </CardTitle>
              <CardDescription>
                {selectedPlugin ? selectedPlugin.name : t("plugins:selectPrompt")}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {!selectedPlugin || isDetailLoading ? (
                <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
                  {isDetailLoading ? t("common:loading") : t("plugins:selectPrompt")}
                </div>
              ) : (
                <>
                  <div className="flex flex-wrap items-center gap-3">
                    <Badge variant="outline">{selectedPlugin.plugin_type}</Badge>
                    <Badge variant="outline">{selectedPlugin.status}</Badge>
                    <Badge variant="outline">
                      {t("plugins:activeVersion")}: {selectedPlugin.active_version?.version || "-"}
                    </Badge>
                    {selectedPlugin.settings_validation_function_name ? (
                      <Badge variant="secondary">
                        {t("plugins:settingsValidator")}: {selectedPlugin.settings_validation_function_name}
                      </Badge>
                    ) : null}
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-xl border border-border/70 p-4 text-sm">
                      <div className="mb-2 flex items-center gap-2 font-medium">
                        <Zap className="size-4 text-primary" />
                        {t("plugins:runtimeState")}
                      </div>
                      <div className="space-y-1 text-muted-foreground">
                        <div>{t("plugins:runtimeStatus")}: {selectedPlugin.run_state?.status || "-"}</div>
                        <div>{t("plugins:runtimeProcess")}: {selectedPlugin.run_state?.process_type || "-"}</div>
                        <div>{t("plugins:runtimePid")}: {selectedPlugin.run_state?.pid ?? "-"}</div>
                        <div>{t("plugins:runtimeHeartbeat")}: {formatTime(selectedPlugin.run_state?.heartbeat_at || null)}</div>
                      </div>
                      {selectedPlugin.run_state?.error_text ? (
                        <div className="mt-3 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive">
                          {selectedPlugin.run_state.error_text}
                        </div>
                      ) : null}
                    </div>
                    <div className="rounded-xl border border-border/70 p-4 text-sm">
                      <div className="mb-2 flex items-center gap-2 font-medium">
                        <Settings2 className="size-4 text-primary" />
                        {t("plugins:actionsTitle")}
                      </div>
                      <div className="space-y-3">
                        <div
                          className={`rounded-xl border p-4 transition ${
                            selectedPlugin.status === "enabled"
                              ? "border-primary/60 bg-primary/5"
                              : "border-destructive/50 bg-destructive/5"
                          } ${!canRun ? "opacity-70" : ""}`}
                        >
                          <div className="flex items-center justify-between gap-4">
                            <div>
                              <div className="text-sm font-semibold">{t("plugins:pluginEnabled")}</div>
                              <div className="mt-1 text-xs text-muted-foreground">
                                {selectedPlugin.status === "enabled" ? t("plugins:enabled") : t("plugins:disabled")}
                              </div>
                            </div>
                            <div className="flex items-center gap-3">
                              <Badge variant={selectedPlugin.status === "enabled" ? "secondary" : "destructive"}>
                                {selectedPlugin.status === "enabled" ? t("plugins:enabled") : t("plugins:disabled")}
                              </Badge>
                              <Switch
                                checked={selectedPlugin.status === "enabled"}
                                disabled={!canRun}
                                onCheckedChange={(checked) => void handleTogglePluginRuntime(checked)}
                              />
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center justify-between rounded-lg border border-border/70 px-3 py-2">
                          <span>{t("plugins:globalVisibility")}</span>
                          <Switch
                            checked={selectedPlugin.is_globally_visible}
                            disabled={!canWrite}
                            onCheckedChange={(checked) => void handleSetGlobalVisibility(checked)}
                          />
                        </div>
                        <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
                          <Button
                            variant="destructive"
                            size="sm"
                            disabled={!canWrite}
                            onClick={() => setIsDeleteDialogOpen(true)}
                          >
                            {t("plugins:deletePlugin")}
                          </Button>
                          <AlertDialogContent size="sm">
                            <AlertDialogHeader>
                              <AlertDialogTitle>{t("plugins:deletePlugin")}</AlertDialogTitle>
                              <AlertDialogDescription>
                                {selectedPlugin
                                  ? t("plugins:deleteConfirm", {
                                      name: selectedPlugin.display_name || selectedPlugin.name,
                                    })
                                  : t("plugins:deletePlugin")}
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel disabled={isDeleting}>{t("common:cancel")}</AlertDialogCancel>
                              <AlertDialogAction
                                variant="destructive"
                                disabled={isDeleting}
                                onClick={() => void handleDeletePlugin()}
                              >
                                {isDeleting ? t("common:saving") : t("common:delete")}
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {selectedPlugin ? (
            <Card className="border-border/70 bg-card/90">
              <CardHeader>
                <CardTitle className="text-base">{t("plugins:globalConfigTitle")}</CardTitle>
                <CardDescription>{t("plugins:globalConfigDescription")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>{t("plugins:globalConfigJson")}</Label>
                  <Textarea
                    rows={10}
                    value={globalConfigDraft}
                    onChange={(event) => {
                      setGlobalConfigDraft(event.target.value);
                      if (globalConfigErrorKey) {
                        setGlobalConfigErrorKey(null);
                      }
                    }}
                  />
                  {globalConfigErrorKey ? (
                    <div className="text-sm text-destructive">{t(`plugins:${globalConfigErrorKey}`)}</div>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button disabled={!canWrite || isSavingConfig} onClick={() => void handleSaveGlobalConfig()}>
                    {isSavingConfig ? t("common:saving") : t("plugins:saveGlobalConfig")}
                  </Button>
                  <Button
                    variant="outline"
                    disabled={!canWrite || isValidatingGlobalConfig}
                    onClick={() => void handleValidateGlobalConfig()}
                  >
                    {isValidatingGlobalConfig ? t("common:saving") : t("plugins:validateGlobalConfig")}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : null}

          {selectedPlugin ? (
            <Card className="border-border/70 bg-card/90">
              <CardHeader>
                <CardTitle className="text-base">{t("plugins:eventConfigTitle")}</CardTitle>
                <CardDescription>{t("plugins:eventConfigDescription")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {selectedPlugin.events.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
                    {t("plugins:noEvents")}
                  </div>
                ) : (
                  selectedPlugin.events.map((event) => (
                    <div key={event.name} className="rounded-xl border border-border/70 p-4">
                      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="font-medium">{event.title || event.name}</div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {t("plugins:eventMeta", {
                              name: event.name,
                              mode: event.mode,
                              functionName: event.function_name,
                              defaultValue: "{{name}} · {{mode}} · {{functionName}}",
                            })}
                          </div>
                        </div>
                        <div
                          className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-sm transition ${
                            event.is_enabled ? "border-primary/50 bg-primary/5" : "border-border/70 bg-muted/20"
                          }`}
                        >
                          <Switch
                            checked={event.is_enabled}
                            disabled={!canRun}
                            onCheckedChange={(checked) => void handleToggleEventEnabled(event.name, checked)}
                          />
                          <span className="font-medium">
                            {event.is_enabled ? t("plugins:enabled") : t("plugins:disabled")}
                          </span>
                        </div>
                      </div>
                      {event.mode === "short_lived" ? (
                        <div className="mb-4 rounded-lg border border-border/70 bg-muted/20 p-3">
                          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                            <div>
                              <div className="text-sm font-medium">{t("plugins:eventScheduleTitle")}</div>
                              <div className="mt-1 text-xs text-muted-foreground">
                                {t("plugins:eventScheduleDescription")}
                              </div>
                            </div>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={!canRun || runningEventName === event.name}
                              onClick={() => void handleRunEventNow(event.name)}
                            >
                              {runningEventName === event.name ? t("common:saving") : t("plugins:runEventNow")}
                            </Button>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {t("plugins:userDescription")}
                          </div>
                        </div>
                      ) : null}
                      <div className="space-y-2">
                        <Textarea
                          rows={8}
                          value={eventConfigDrafts[event.name] || "{}"}
                          onChange={(eventTarget) => {
                            const next = eventTarget.target.value;
                            setEventConfigDrafts((prev) => ({ ...prev, [event.name]: next }));
                            if (eventConfigErrorKeys[event.name]) {
                              setEventConfigErrorKeys((prev) => ({ ...prev, [event.name]: null }));
                            }
                          }}
                        />
                        {eventConfigErrorKeys[event.name] ? (
                          <div className="text-sm text-destructive">
                            {t(`plugins:${eventConfigErrorKeys[event.name]}`)}
                          </div>
                        ) : null}
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            disabled={!canWrite || isSavingConfig}
                            onClick={() => void handleSaveEventConfig(event.name)}
                          >
                            {isSavingConfig ? t("common:saving") : t("plugins:saveEventConfig")}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              setEventConfigDrafts((prev) => ({
                                ...prev,
                                [event.name]: formatJson(event.default_config_json),
                              }))
                            }
                          >
                            {t("plugins:resetEventConfig")}
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          ) : null}

          {selectedPlugin ? (
            <Card className="border-border/70 bg-card/90">
              <CardHeader>
                <CardTitle className="text-base">{t("plugins:groupVisibilityTitle")}</CardTitle>
                <CardDescription>{t("plugins:groupVisibilityDescription")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 md:grid-cols-[1fr_auto_auto] md:items-end">
                  <div className="grid gap-2">
                    <Label>{t("plugins:groupField")}</Label>
                    <PopupSelect
                      title={t("plugins:selectGroup")}
                      description={t("plugins:groupVisibilityDescription")}
                      placeholder={t("plugins:selectGroup")}
                      searchPlaceholder={t("common:search")}
                      emptyText={t("plugins:noGroupVisibility")}
                      value={selectedGroupId}
                      onValueChange={setSelectedGroupId}
                      options={groupOptions}
                    />
                  </div>
                  <div className="flex h-10 items-center gap-2 rounded-lg border border-border/70 px-3 text-sm">
                    {newGroupVisibility ? <Eye className="size-4" /> : <EyeOff className="size-4" />}
                    <Switch checked={newGroupVisibility} onCheckedChange={setNewGroupVisibility} />
                    <span>{newGroupVisibility ? t("plugins:visible") : t("plugins:hidden")}</span>
                  </div>
                  <Button
                    disabled={!selectedGroupId || !canWrite || isGroupSaving}
                    onClick={() => void handleSetGroupVisibility()}
                  >
                    {isGroupSaving ? t("common:saving") : t("plugins:applyGroupVisibility")}
                  </Button>
                </div>

                {groupVisibility.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
                    {t("plugins:noGroupVisibility")}
                  </div>
                ) : (
                  groupVisibility.map((row) => (
                    <div key={row.id} className="rounded-xl border border-border/70 p-4 text-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="font-medium">{groupNameByActualId.get(row.group_id) || row.group_id}</div>
                        <Badge variant={row.is_visible ? "secondary" : "outline"}>
                          {row.is_visible ? t("plugins:visible") : t("plugins:hidden")}
                        </Badge>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {t("plugins:updatedAt")}: {formatTime(row.updated_at)}
                      </div>
                    </div>
                  ))
                )}
                <div className="rounded-lg border border-border/70 bg-muted/20 p-3 text-xs text-muted-foreground">
                  <div className="flex items-start gap-2">
                    <ShieldAlert className="mt-0.5 size-4 shrink-0" />
                    <span>{t("plugins:bootstrapAdminHint")}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : null}

          <Collapsible open={isSharedLibsOpen} onOpenChange={setIsSharedLibsOpen}>
            <Card className="border-border/70 bg-card/90">
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle className="text-base">{t("plugins:sharedLibTitle")}</CardTitle>
                    <CardDescription>{t("plugins:sharedLibDescription")}</CardDescription>
                  </div>
                  <CollapsibleTrigger asChild>
                    <Button variant="ghost" size="sm">
                      <ChevronDown className={`size-4 transition-transform ${isSharedLibsOpen ? "rotate-180" : ""}`} />
                    </Button>
                  </CollapsibleTrigger>
                </div>
              </CardHeader>
              <CollapsibleContent>
                <CardContent className="space-y-2">
                  {sharedPackages.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
                      {t("plugins:sharedLibEmpty")}
                    </div>
                  ) : (
                    sharedPackages.map((item) => (
                      <div key={`${item.normalized_name}@${item.version}`} className="rounded-xl border border-border/70 p-4 text-sm">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="font-medium">{item.name}</div>
                          <Badge variant="outline">{item.version}</Badge>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                          <span>{t("plugins:referenceCount", { count: item.reference_count })}</span>
                          <span>{t("plugins:sizeBytes", { value: item.size_bytes })}</span>
                        </div>
                      </div>
                    ))
                  )}
                </CardContent>
              </CollapsibleContent>
            </Card>
          </Collapsible>
        </div>
      </div>
    </PageFrame>
  );
}
