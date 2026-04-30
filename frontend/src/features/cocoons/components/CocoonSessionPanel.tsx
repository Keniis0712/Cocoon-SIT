import { Plus, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { TagRead } from "@/api/types/catalog";
import type { CocoonRead } from "@/api/types/cocoons";
import type { AvailableModelRead } from "@/api/types/providers";
import type { WakeupTaskRead } from "@/api/types/wakeups";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatWorkspaceTime } from "@/features/workspace/utils";

const DEFAULT_RELATION_SCORE = 50;

type CocoonSessionPanelProps = {
  selectedCocoon: CocoonRead | null;
  providerModels: AvailableModelRead[];
  sessionActiveTags: string[];
  selectedTagIds: number[];
  availableAddableTags: TagRead[];
  addTagValue: string;
  isUpdatingTags: boolean;
  currentModelId: number | null | undefined;
  dispatchState: string | null | undefined;
  relationScore: number | null | undefined;
  currentAiWakeup: WakeupTaskRead | null;
  debounceUntil: string | null | undefined;
  dispatchReason: string | null | undefined;
  lastError: string | null | undefined;
  onRemoveTag: (tagId: number) => void;
  onAddTag: (value: string) => void;
  onChangeModel: (modelId: string) => void;
};

export function CocoonSessionPanel({
  selectedCocoon,
  providerModels,
  sessionActiveTags,
  selectedTagIds,
  availableAddableTags,
  addTagValue,
  isUpdatingTags,
  currentModelId,
  dispatchState,
  relationScore,
  currentAiWakeup,
  debounceUntil,
  dispatchReason,
  lastError,
  onRemoveTag,
  onAddTag,
  onChangeModel,
}: CocoonSessionPanelProps) {
  const { t } = useTranslation(["workspace", "wakeups", "common"]);
  const tagLabelByKey = new Map<string, string>();
  for (const tag of (selectedCocoon?.tags || []).filter((item) => !item.is_system)) {
    tagLabelByKey.set(String(tag.id), tag.name);
    tagLabelByKey.set(tag.actual_id, tag.name);
    tagLabelByKey.set(tag.tag_id, tag.name);
    tagLabelByKey.set(tag.name, tag.name);
  }
  const activeTags = sessionActiveTags.length
    ? sessionActiveTags
        .filter((tag) => tagLabelByKey.has(tag))
        .map((tag) => ({ key: tag, label: tagLabelByKey.get(tag) || tag }))
    : selectedCocoon?.tags?.filter((item) => !item.is_system).map((item) => ({ key: item.actual_id, label: item.name })) || [];
  const visibleSelectedTags = (selectedCocoon?.tags || []).filter((tag) => !tag.is_system);
  const displayTags = visibleSelectedTags.length
    ? visibleSelectedTags.map((tag) => ({ key: tag.actual_id, label: tag.name, id: tag.id }))
    : activeTags.map((tag) => ({ ...tag, id: null }));

  return (
    <Card className="border-border/70 bg-card/90">
      <CardHeader>
        <CardTitle>{t("workspace:sessionTitle")}</CardTitle>
        <CardDescription>{t("workspace:sessionDescription")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="mb-2 text-sm text-muted-foreground">{t("workspace:editChatTags")}</div>
          <div className="rounded-2xl border border-border/70 bg-background/60 p-3">
            <div className="flex flex-wrap gap-2">
              {displayTags.map((tag) => (
                tag.id !== null ? (
                  <button
                    key={tag.key}
                    type="button"
                    className="inline-flex items-center rounded-full"
                    onClick={() => onRemoveTag(tag.id)}
                    disabled={isUpdatingTags}
                  >
                    <Badge variant="secondary">
                      <span className="inline-flex items-center gap-1">
                        {tag.label}
                        <X className="size-3" />
                      </span>
                    </Badge>
                  </button>
                ) : (
                  <Badge key={tag.key} variant="secondary">
                    {tag.label}
                  </Badge>
                )
              ))}
              {!displayTags.length ? <span className="text-sm text-muted-foreground">{t("workspace:noTagsEnabled")}</span> : null}
            </div>
            <div className="mt-3 text-xs text-muted-foreground">{t("workspace:editTagsHint")}</div>
            <div className="mt-3">
              <Select value={addTagValue} onValueChange={onAddTag} disabled={isUpdatingTags || !availableAddableTags.length}>
                <SelectTrigger>
                  <SelectValue placeholder={t("workspace:addTag")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__add">
                    <span className="inline-flex items-center gap-2">
                      <Plus className="size-4" />
                      {t("workspace:addTag")}
                    </span>
                  </SelectItem>
                  {availableAddableTags.map((tag) => (
                    <SelectItem key={tag.id} value={String(tag.id)}>
                      {tag.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
        <div>
          <div className="mb-2 text-sm text-muted-foreground">{t("workspace:currentModel")}</div>
          <Select value={String(currentModelId || selectedCocoon?.selected_model_id || "")} onValueChange={onChangeModel}>
            <SelectTrigger>
              <SelectValue placeholder={t("common:selectModel")} />
            </SelectTrigger>
            <SelectContent>
              {providerModels.map((model) => (
                <SelectItem key={model.id} value={String(model.id)}>
                  {model.model_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="rounded-2xl border border-border/70 bg-background/70 p-3 text-sm">
          <div className="mb-2 text-muted-foreground">{t("workspace:state")}</div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">{t("workspace:dispatch", { value: dispatchState || selectedCocoon?.dispatch_status || "idle" })}</Badge>
            <Badge variant="outline">{t("workspace:relation", { value: relationScore ?? DEFAULT_RELATION_SCORE })}</Badge>
            <Badge variant="outline">{t("wakeups:aiWakeupBadge", { value: currentAiWakeup ? t("wakeups:scheduled") : t("wakeups:none") })}</Badge>
          </div>
          {currentAiWakeup ? (
            <div className="mt-3 space-y-1 text-xs text-muted-foreground">
              <div>{t("wakeups:aiWakeupAt", { value: formatWorkspaceTime(currentAiWakeup.run_at) })}</div>
              <div>{t("wakeups:aiWakeupReason", { value: currentAiWakeup.reason || t("wakeups:unknownWakeupReason") })}</div>
            </div>
          ) : (
            <div className="mt-3 text-xs text-muted-foreground">{t("wakeups:noAiWakeup")}</div>
          )}
          {debounceUntil ? <div className="mt-3 text-xs text-muted-foreground">{t("workspace:debouncedUntil", { value: formatWorkspaceTime(debounceUntil) })}</div> : null}
          {dispatchReason ? <div className="mt-3 text-xs text-muted-foreground">{dispatchReason}</div> : null}
          {lastError ? <div className="mt-3 text-sm text-destructive">{lastError}</div> : null}
        </div>
      </CardContent>
    </Card>
  );
}
