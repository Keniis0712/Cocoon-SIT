import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Link2, Plug, RefreshCcw, Settings2, ShieldAlert, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { listChatGroups } from "@/api/chatGroups";
import { showErrorToast } from "@/api/client";
import { getCocoons } from "@/api/cocoons";
import {
  addWorkspacePluginTargetBinding,
  clearChatGroupPluginError,
  clearWorkspacePluginError,
  deleteWorkspacePluginTargetBinding,
  getChatGroupPluginConfig,
  listWorkspacePluginTargetBindings,
  listWorkspacePlugins,
  setChatGroupPluginEnabled,
  setWorkspacePluginEnabled,
  updateChatGroupPluginConfig,
  updateWorkspacePluginConfig,
  validateChatGroupPluginConfig,
  validateWorkspacePluginConfig,
} from "@/api/plugins";
import type { ChatGroupRead, CocoonRead } from "@/api/types";
import type { ChatGroupPluginConfigRead, PluginTargetBindingRead, UserPluginRead } from "@/api/types/plugins";
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
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

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

type SchemaProperty = {
  type?: string | string[];
  title?: string;
  description?: string;
  default?: unknown;
  enum?: unknown[];
  minimum?: number;
  maximum?: number;
};

function schemaProperties(schema: Record<string, unknown>): Record<string, SchemaProperty> {
  const properties = schema.properties;
  if (!properties || typeof properties !== "object" || Array.isArray(properties)) {
    return {};
  }
  return properties as Record<string, SchemaProperty>;
}

function schemaRequired(schema: Record<string, unknown>): string[] {
  return Array.isArray(schema.required) ? schema.required.filter((item): item is string => typeof item === "string") : [];
}

function isMultilineField(key: string, property: SchemaProperty) {
  const text = `${key} ${property.title || ""} ${property.description || ""}`.toLowerCase();
  return text.includes("pem") || text.includes("private") || text.includes("secret") || text.includes("token");
}

function fieldType(property: SchemaProperty) {
  return Array.isArray(property.type) ? property.type.find((item) => item !== "null") : property.type;
}

function ConfigSchemaDialog({
  open,
  title,
  description,
  schema,
  value,
  defaultValue,
  isSaving,
  isValidating,
  onOpenChange,
  onSave,
  onValidate,
}: {
  open: boolean;
  title: string;
  description: string;
  schema: Record<string, unknown>;
  value: Record<string, unknown>;
  defaultValue: Record<string, unknown>;
  isSaving: boolean;
  isValidating: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (value: Record<string, unknown>) => void | Promise<void>;
  onValidate: () => void | Promise<void>;
}) {
  const { t } = useTranslation(["plugins", "common"]);
  const properties = useMemo(() => schemaProperties(schema), [schema]);
  const required = useMemo(() => new Set(schemaRequired(schema)), [schema]);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [jsonDraft, setJsonDraft] = useState("{}");
  const [jsonError, setJsonError] = useState<string | null>(null);
  const hasSchemaFields = Object.keys(properties).length > 0;

  useEffect(() => {
    if (!open) {
      return;
    }
    setDraft({ ...(defaultValue || {}), ...(value || {}) });
    setJsonDraft(formatJson(value));
    setJsonError(null);
  }, [defaultValue, open, value]);

  function updateField(key: string, next: unknown) {
    setDraft((prev) => ({ ...prev, [key]: next }));
  }

  function resetToDefaults() {
    setDraft({ ...(defaultValue || {}) });
    setJsonDraft(formatJson(defaultValue));
    setJsonError(null);
  }

  function handleSave() {
    if (hasSchemaFields) {
      void onSave(draft);
      return;
    }
    const parsed = parseJson(jsonDraft);
    if (!parsed.value) {
      setJsonError(t(`plugins:${parsed.errorKey || "jsonInvalid"}`));
      return;
    }
    setJsonError(null);
    void onSave(parsed.value);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        {hasSchemaFields ? (
          <div className="grid gap-4">
            {Object.entries(properties).map(([key, property]) => {
              const type = fieldType(property);
              const label = property.title || key;
              const value = draft[key] ?? property.default ?? "";
              return (
                <div key={key} className="grid gap-2">
                  <Label htmlFor={`plugin-config-${key}`}>
                    {label}
                    {required.has(key) ? <span className="text-destructive"> *</span> : null}
                  </Label>
                  {property.enum ? (
                    <Select value={String(value ?? "")} onValueChange={(next) => updateField(key, next)}>
                      <SelectTrigger id={`plugin-config-${key}`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {property.enum.map((option) => (
                          <SelectItem key={String(option)} value={String(option)}>
                            {String(option)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : type === "boolean" ? (
                    <div className="flex h-9 items-center gap-2 rounded-lg border border-border/70 px-3">
                      <Checkbox
                        id={`plugin-config-${key}`}
                        checked={Boolean(value)}
                        onCheckedChange={(checked) => updateField(key, checked === true)}
                      />
                      <span className="text-sm">{Boolean(value) ? t("plugins:enabled") : t("plugins:disabled")}</span>
                    </div>
                  ) : type === "integer" || type === "number" ? (
                    <Input
                      id={`plugin-config-${key}`}
                      type="number"
                      min={property.minimum}
                      max={property.maximum}
                      value={typeof value === "number" ? String(value) : String(value || "")}
                      onChange={(event) => {
                        const raw = event.target.value;
                        updateField(key, raw === "" ? "" : type === "integer" ? Number.parseInt(raw, 10) : Number(raw));
                      }}
                    />
                  ) : isMultilineField(key, property) ? (
                    <Textarea
                      id={`plugin-config-${key}`}
                      rows={5}
                      value={String(value ?? "")}
                      onChange={(event) => updateField(key, event.target.value)}
                    />
                  ) : (
                    <Input
                      id={`plugin-config-${key}`}
                      value={String(value ?? "")}
                      onChange={(event) => updateField(key, event.target.value)}
                    />
                  )}
                  {property.description ? (
                    <div className="text-xs text-muted-foreground">{property.description}</div>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="grid gap-2">
            <Label>{t("plugins:configJsonFallback")}</Label>
            <Textarea
              rows={12}
              value={jsonDraft}
              onChange={(event) => {
                setJsonDraft(event.target.value);
                setJsonError(null);
              }}
            />
            {jsonError ? <div className="text-sm text-destructive">{jsonError}</div> : null}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={resetToDefaults}>
            {t("plugins:resetUserConfig")}
          </Button>
          <Button variant="outline" disabled={isValidating} onClick={() => void onValidate()}>
            {isValidating ? t("common:saving") : t("plugins:validateUserConfig")}
          </Button>
          <Button disabled={isSaving} onClick={handleSave}>
            {isSaving ? t("common:saving") : t("common:save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function PluginsPage() {
  const { t } = useTranslation(["plugins", "common"]);
  const [plugins, setPlugins] = useState<UserPluginRead[]>([]);
  const [selectedPluginId, setSelectedPluginId] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isClearingError, setIsClearingError] = useState(false);
  const [isBindingLoading, setIsBindingLoading] = useState(false);
  const [isBindingSaving, setIsBindingSaving] = useState(false);
  const [isGroupConfigLoading, setIsGroupConfigLoading] = useState(false);
  const [isGroupConfigSaving, setIsGroupConfigSaving] = useState(false);
  const [isGroupConfigValidating, setIsGroupConfigValidating] = useState(false);
  const [isGroupErrorClearing, setIsGroupErrorClearing] = useState(false);
  const [isUserConfigDialogOpen, setIsUserConfigDialogOpen] = useState(false);
  const [isGroupConfigDialogOpen, setIsGroupConfigDialogOpen] = useState(false);
  const [groupConfig, setGroupConfig] = useState<ChatGroupPluginConfigRead | null>(null);
  const [targetBindings, setTargetBindings] = useState<PluginTargetBindingRead[]>([]);
  const [cocoons, setCocoons] = useState<CocoonRead[]>([]);
  const [chatGroups, setChatGroups] = useState<ChatGroupRead[]>([]);
  const [bindingTargetType, setBindingTargetType] = useState<"cocoon" | "chat_group">("cocoon");
  const [selectedCocoonId, setSelectedCocoonId] = useState("");
  const [selectedChatGroupId, setSelectedChatGroupId] = useState("");

  const selectedPlugin = useMemo(
    () => plugins.find((item) => item.id === selectedPluginId) ?? null,
    [plugins, selectedPluginId],
  );
  const cocoonOptions = useMemo(
    () =>
      cocoons.map((cocoon) => ({
        value: String(cocoon.id),
        label: cocoon.name,
        description: String(cocoon.id),
        keywords: [String(cocoon.id)],
      })),
    [cocoons],
  );
  const chatGroupOptions = useMemo(
    () =>
      chatGroups.map((room) => ({
        value: room.id,
        label: room.name,
        description: room.id,
        keywords: [room.id],
      })),
    [chatGroups],
  );

  useEffect(() => {
    void loadPlugins();
    void loadTargets();
  }, []);

  useEffect(() => {
    if (!selectedPluginId) {
      setTargetBindings([]);
      return;
    }
    void loadTargetBindings(selectedPluginId);
  }, [selectedPluginId]);

  useEffect(() => {
    if (!selectedPluginId || !selectedChatGroupId) {
      setGroupConfig(null);
      return;
    }
    void loadGroupConfig(selectedPluginId, selectedChatGroupId);
  }, [selectedPluginId, selectedChatGroupId]);

  useEffect(() => {
    if (!selectedCocoonId && cocoons[0]) {
      setSelectedCocoonId(String(cocoons[0].id));
    }
  }, [cocoons, selectedCocoonId]);

  useEffect(() => {
    if (!selectedChatGroupId && chatGroups[0]) {
      setSelectedChatGroupId(chatGroups[0].id);
    }
  }, [chatGroups, selectedChatGroupId]);

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

  async function loadTargets() {
    try {
      const [cocoonPage, rooms] = await Promise.all([
        getCocoons(1, 200, "mine"),
        listChatGroups(),
      ]);
      setCocoons(cocoonPage.items);
      setChatGroups(rooms);
    } catch (error) {
      showErrorToast(error, t("plugins:loadFailed"));
    }
  }

  async function loadTargetBindings(pluginId: string) {
    setIsBindingLoading(true);
    try {
      setTargetBindings(await listWorkspacePluginTargetBindings(pluginId));
    } catch (error) {
      showErrorToast(error, t("plugins:loadFailed"));
    } finally {
      setIsBindingLoading(false);
    }
  }

  async function loadGroupConfig(pluginId: string, chatGroupId: string) {
    setIsGroupConfigLoading(true);
    try {
      const item = await getChatGroupPluginConfig(pluginId, chatGroupId);
      setGroupConfig(item);
    } catch (error) {
      setGroupConfig(null);
      showErrorToast(error, t("plugins:loadFailed"));
    } finally {
      setIsGroupConfigLoading(false);
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

  async function handleSaveConfig(configJson: Record<string, unknown>) {
    if (!selectedPlugin) {
      return;
    }
    setIsSaving(true);
    try {
      const updated = await updateWorkspacePluginConfig(selectedPlugin.id, configJson);
      patchPlugin(updated);
      setIsUserConfigDialogOpen(false);
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

  async function handleAddTargetBinding() {
    if (!selectedPlugin) {
      return;
    }
    const targetId = bindingTargetType === "cocoon" ? selectedCocoonId : selectedChatGroupId;
    if (!targetId) {
      return;
    }
    setIsBindingSaving(true);
    try {
      const created = await addWorkspacePluginTargetBinding(selectedPlugin.id, bindingTargetType, targetId);
      setTargetBindings((prev) => {
        if (prev.some((item) => item.id === created.id)) {
          return prev.map((item) => (item.id === created.id ? created : item));
        }
        return [...prev, created];
      });
      toast.success(t("plugins:targetBindingSuccess"));
    } catch (error) {
      showErrorToast(error, t("plugins:targetBindingFailed"));
    } finally {
      setIsBindingSaving(false);
    }
  }

  async function handleDeleteTargetBinding(bindingId: string) {
    if (!selectedPlugin) {
      return;
    }
    setIsBindingSaving(true);
    try {
      await deleteWorkspacePluginTargetBinding(selectedPlugin.id, bindingId);
      setTargetBindings((prev) => prev.filter((item) => item.id !== bindingId));
      toast.success(t("plugins:targetUnbindingSuccess"));
    } catch (error) {
      showErrorToast(error, t("plugins:targetUnbindingFailed"));
    } finally {
      setIsBindingSaving(false);
    }
  }

  async function handleToggleGroupEnabled(nextEnabled: boolean) {
    if (!selectedPlugin || !selectedChatGroupId) {
      return;
    }
    setIsGroupConfigSaving(true);
    try {
      const updated = await setChatGroupPluginEnabled(selectedPlugin.id, selectedChatGroupId, nextEnabled);
      setGroupConfig(updated);
      toast.success(t("plugins:groupConfigSaveSuccess"));
    } catch (error) {
      showErrorToast(error, t("plugins:groupConfigSaveFailed"));
    } finally {
      setIsGroupConfigSaving(false);
    }
  }

  async function handleSaveGroupConfig(configJson: Record<string, unknown>) {
    if (!selectedPlugin || !selectedChatGroupId) {
      return;
    }
    setIsGroupConfigSaving(true);
    try {
      const updated = await updateChatGroupPluginConfig(selectedPlugin.id, selectedChatGroupId, configJson);
      setGroupConfig(updated);
      setIsGroupConfigDialogOpen(false);
      toast.success(t("plugins:groupConfigSaveSuccess"));
    } catch (error) {
      showErrorToast(error, t("plugins:groupConfigSaveFailed"));
    } finally {
      setIsGroupConfigSaving(false);
    }
  }

  async function handleValidateGroupConfig() {
    if (!selectedPlugin || !selectedChatGroupId) {
      return;
    }
    setIsGroupConfigValidating(true);
    try {
      const updated = await validateChatGroupPluginConfig(selectedPlugin.id, selectedChatGroupId);
      setGroupConfig(updated);
      if (updated.error_text) {
        toast.error(updated.error_text);
      } else {
        toast.success(t("plugins:validateSuccess"));
      }
    } catch (error) {
      showErrorToast(error, t("plugins:validateFailed"));
    } finally {
      setIsGroupConfigValidating(false);
    }
  }

  async function handleClearGroupError() {
    if (!selectedPlugin || !selectedChatGroupId) {
      return;
    }
    setIsGroupErrorClearing(true);
    try {
      const updated = await clearChatGroupPluginError(selectedPlugin.id, selectedChatGroupId);
      setGroupConfig(updated);
      toast.success(t("plugins:clearErrorSuccess"));
    } catch (error) {
      showErrorToast(error, t("plugins:clearErrorFailed"));
    } finally {
      setIsGroupErrorClearing(false);
    }
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
                <div className="space-y-3">
                  <div
                    className={`rounded-xl border p-4 transition ${
                      selectedPlugin.is_enabled
                        ? "border-primary/60 bg-primary/5"
                        : "border-destructive/50 bg-destructive/5"
                    } ${isSaving ? "opacity-70" : ""}`}
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <div className="text-sm font-semibold">{t("plugins:enabledForMe")}</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {selectedPlugin.is_enabled ? t("plugins:enabled") : t("plugins:disabled")}
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge variant={selectedPlugin.is_enabled ? "secondary" : "destructive"}>
                          {selectedPlugin.is_enabled ? t("plugins:enabled") : t("plugins:disabled")}
                        </Badge>
                        <Switch
                          checked={selectedPlugin.is_enabled}
                          disabled={isSaving}
                          onCheckedChange={(checked) => void handleToggleEnabled(checked)}
                        />
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <Badge variant="outline">{selectedPlugin.plugin_type}</Badge>
                    <Badge variant="outline">{selectedPlugin.status}</Badge>
                  </div>
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

                <div className="rounded-xl border border-border/70 p-4">
                  <div className="flex items-start gap-3">
                    <Link2 className="mt-0.5 size-4 text-primary" />
                    <div>
                      <div className="font-medium">{t("plugins:targetBindingTitle")}</div>
                      <div className="mt-1 text-sm text-muted-foreground">
                        {t("plugins:targetBindingDescription")}
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3 md:grid-cols-[170px_1fr_auto] md:items-end">
                    <div className="grid gap-2">
                      <Label>{t("plugins:targetType")}</Label>
                      <Select
                        value={bindingTargetType}
                        onValueChange={(value) => setBindingTargetType(value as "cocoon" | "chat_group")}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="cocoon">{t("plugins:targetCocoon")}</SelectItem>
                          <SelectItem value="chat_group">{t("plugins:targetChatGroup")}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="grid gap-2">
                      <Label>{t("plugins:targetObject")}</Label>
                      {bindingTargetType === "cocoon" ? (
                        <PopupSelect
                          title={t("plugins:selectCocoon")}
                          description={t("plugins:targetBindingDescription")}
                          placeholder={t("plugins:selectCocoon")}
                          searchPlaceholder={t("common:search")}
                          emptyText={t("plugins:noTargetBindings")}
                          value={selectedCocoonId}
                          onValueChange={setSelectedCocoonId}
                          options={cocoonOptions}
                        />
                      ) : (
                        <PopupSelect
                          title={t("plugins:selectChatGroup")}
                          description={t("plugins:targetBindingDescription")}
                          placeholder={t("plugins:selectChatGroup")}
                          searchPlaceholder={t("common:search")}
                          emptyText={t("plugins:noChatGroups")}
                          value={selectedChatGroupId}
                          onValueChange={setSelectedChatGroupId}
                          options={chatGroupOptions}
                        />
                      )}
                    </div>

                    <Button
                      disabled={
                        isBindingSaving ||
                        (bindingTargetType === "cocoon" ? !selectedCocoonId : !selectedChatGroupId)
                      }
                      onClick={() => void handleAddTargetBinding()}
                    >
                      {isBindingSaving ? t("common:saving") : t("plugins:addTargetBinding")}
                    </Button>
                  </div>

                  <div className="mt-4 space-y-3">
                    {isBindingLoading ? (
                      <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
                        {t("common:loading")}
                      </div>
                    ) : targetBindings.length === 0 ? (
                      <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
                        {t("plugins:noTargetBindings")}
                      </div>
                    ) : (
                      targetBindings.map((binding) => (
                        <div
                          key={binding.id}
                          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border/70 p-3 text-sm"
                        >
                          <div>
                            <div className="font-medium">{binding.target_name}</div>
                            <div className="mt-1 text-xs text-muted-foreground">
                              {binding.target_type === "cocoon" ? t("plugins:targetCocoon") : t("plugins:targetChatGroup")} - {binding.target_id}
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={isBindingSaving}
                            onClick={() => void handleDeleteTargetBinding(binding.id)}
                          >
                            <Trash2 className="mr-2 size-4" />
                            {t("plugins:removeTargetBinding")}
                          </Button>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-border/70 p-4">
                  <div className="flex items-start gap-3">
                    <ShieldAlert className="mt-0.5 size-4 text-primary" />
                    <div>
                      <div className="font-medium">{t("plugins:groupConfigTitle")}</div>
                      <div className="mt-1 text-sm text-muted-foreground">
                        {t("plugins:groupConfigDescription")}
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
                    <div className="grid gap-2">
                      <Label>{t("plugins:targetChatGroup")}</Label>
                      <PopupSelect
                        title={t("plugins:selectChatGroup")}
                        description={t("plugins:groupConfigDescription")}
                        placeholder={t("plugins:selectChatGroup")}
                        searchPlaceholder={t("common:search")}
                        emptyText={t("plugins:noChatGroups")}
                        value={selectedChatGroupId}
                        onValueChange={setSelectedChatGroupId}
                        options={chatGroupOptions}
                      />
                    </div>
                    <div
                      className={`flex items-center justify-between gap-3 rounded-xl border px-4 py-3 text-sm transition ${
                        groupConfig?.is_enabled ?? true
                          ? "border-primary/50 bg-primary/5"
                          : "border-destructive/40 bg-destructive/5"
                      }`}
                    >
                      <div>
                        <div className="font-medium">{t("plugins:enabledForGroup")}</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {groupConfig?.is_enabled ?? true ? t("plugins:enabled") : t("plugins:disabled")}
                        </div>
                      </div>
                      <Switch
                        checked={groupConfig?.is_enabled ?? true}
                        disabled={!selectedChatGroupId || isGroupConfigSaving || isGroupConfigLoading}
                        onCheckedChange={(checked) => void handleToggleGroupEnabled(checked)}
                      />
                    </div>
                  </div>

                  {isGroupConfigLoading ? (
                    <div className="mt-4 rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
                      {t("common:loading")}
                    </div>
                  ) : chatGroups.length === 0 ? (
                    <div className="mt-4 rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
                      {t("plugins:noChatGroups")}
                    </div>
                  ) : (
                    <div className="mt-4 space-y-3">
                      {groupConfig?.error_text ? (
                        <div className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm">
                          <div className="mb-2 flex items-center gap-2 font-medium text-destructive">
                            <ShieldAlert className="size-4" />
                            {t("plugins:groupErrorTitle")}
                          </div>
                          <div className="whitespace-pre-wrap break-words text-foreground/90">
                            {groupConfig.error_text}
                          </div>
                          <div className="mt-2 text-xs text-muted-foreground">
                            {t("plugins:errorUpdatedAt", { value: formatTime(groupConfig.error_at) })}
                          </div>
                          <Button
                            className="mt-3"
                            variant="outline"
                            size="sm"
                            disabled={isGroupErrorClearing}
                            onClick={() => void handleClearGroupError()}
                          >
                            {isGroupErrorClearing ? t("common:saving") : t("plugins:clearUserError")}
                          </Button>
                        </div>
                      ) : null}

                      <div className="flex flex-wrap gap-2">
                        <Button disabled={isGroupConfigSaving} onClick={() => setIsGroupConfigDialogOpen(true)}>
                          <Settings2 className="mr-2 size-4" />
                          {t("plugins:configureGroupSettings")}
                        </Button>
                        <Button
                          variant="outline"
                          disabled={isGroupConfigValidating}
                          onClick={() => void handleValidateGroupConfig()}
                        >
                          {isGroupConfigValidating ? t("common:saving") : t("plugins:validateUserConfig")}
                        </Button>
                      </div>
                    </div>
                  )}
                </div>

                <div className="rounded-xl border border-border/70 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="font-medium">{t("plugins:userConfigLabel")}</div>
                      <div className="mt-1 text-sm text-muted-foreground">
                        {t("plugins:userConfigDialogDescription")}
                      </div>
                    </div>
                    <Button disabled={isSaving} onClick={() => setIsUserConfigDialogOpen(true)}>
                      <Settings2 className="mr-2 size-4" />
                      {t("plugins:configureUserSettings")}
                  </Button>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" disabled={isValidating} onClick={() => void handleValidateConfig()}>
                    {isValidating ? t("common:saving") : t("plugins:validateUserConfig")}
                  </Button>
                </div>

                <ConfigSchemaDialog
                  open={isUserConfigDialogOpen}
                  title={t("plugins:configureUserSettings")}
                  description={t("plugins:userConfigDialogDescription")}
                  schema={selectedPlugin.user_config_schema_json}
                  value={selectedPlugin.user_config_json}
                  defaultValue={selectedPlugin.user_default_config_json}
                  isSaving={isSaving}
                  isValidating={isValidating}
                  onOpenChange={setIsUserConfigDialogOpen}
                  onSave={handleSaveConfig}
                  onValidate={handleValidateConfig}
                />
                <ConfigSchemaDialog
                  open={isGroupConfigDialogOpen}
                  title={t("plugins:configureGroupSettings")}
                  description={t("plugins:groupConfigDescription")}
                  schema={groupConfig?.config_schema_json ?? selectedPlugin.user_config_schema_json}
                  value={groupConfig?.config_json ?? selectedPlugin.user_default_config_json}
                  defaultValue={groupConfig?.default_config_json ?? selectedPlugin.user_default_config_json}
                  isSaving={isGroupConfigSaving}
                  isValidating={isGroupConfigValidating}
                  onOpenChange={setIsGroupConfigDialogOpen}
                  onSave={handleSaveGroupConfig}
                  onValidate={handleValidateGroupConfig}
                />
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </PageFrame>
  );
}
