import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { TagRead } from "@/api/types/catalog";
import type { CocoonRead } from "@/api/types/cocoons";
import type { AvailableModelRead } from "@/api/types/providers";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatWorkspaceTime } from "@/features/workspace/utils";

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
  currentWakeupTaskId: string | null | undefined;
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
  currentWakeupTaskId,
  debounceUntil,
  dispatchReason,
  lastError,
  onRemoveTag,
  onAddTag,
  onChangeModel,
}: CocoonSessionPanelProps) {
  const { t } = useTranslation(["workspace", "common"]);

  return (
    <Card className="border-border/70 bg-card/90">
      <CardHeader>
        <CardTitle>{t("workspace:sessionTitle")}</CardTitle>
        <CardDescription>{t("workspace:sessionDescription")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="mb-2 text-sm text-muted-foreground">{t("workspace:activeTags")}</div>
          <div className="flex flex-wrap gap-2">
            {(sessionActiveTags.length ? sessionActiveTags : selectedCocoon?.tags?.map((item) => item.name) || []).map((tag) => (
              <Badge key={tag} variant="secondary">
                {tag}
              </Badge>
            ))}
            {!(sessionActiveTags.length || selectedCocoon?.tags?.length) ? <span className="text-sm text-muted-foreground">{t("workspace:noTags")}</span> : null}
          </div>
        </div>
        <div>
          <div className="mb-2 text-sm text-muted-foreground">{t("workspace:editChatTags")}</div>
          <div className="rounded-2xl border border-border/70 bg-background/60 p-3">
            <div className="flex flex-wrap gap-2">
              {(selectedCocoon?.tags || []).map((tag) => (
                <button
                  key={tag.id}
                  type="button"
                  className="inline-flex items-center rounded-full"
                  onClick={() => onRemoveTag(tag.id)}
                  disabled={isUpdatingTags}
                >
                  <Badge variant="secondary">{tag.name} x</Badge>
                </button>
              ))}
              {!selectedCocoon?.tags?.length ? <span className="text-sm text-muted-foreground">{t("workspace:noTagsEnabled")}</span> : null}
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
            <Badge variant="outline">{t("workspace:relation", { value: relationScore ?? "-" })}</Badge>
            <Badge variant="outline">{t("workspace:wakeup", { value: currentWakeupTaskId ? `#${currentWakeupTaskId}` : "none" })}</Badge>
          </div>
          {debounceUntil ? <div className="mt-3 text-xs text-muted-foreground">{t("workspace:debouncedUntil", { value: formatWorkspaceTime(debounceUntil) })}</div> : null}
          {dispatchReason ? <div className="mt-3 text-xs text-muted-foreground">{dispatchReason}</div> : null}
          {lastError ? <div className="mt-3 text-sm text-destructive">{lastError}</div> : null}
        </div>
      </CardContent>
    </Card>
  );
}
