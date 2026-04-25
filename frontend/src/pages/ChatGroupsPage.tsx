import { useEffect, useMemo, useState } from "react";
import { ArrowRight, MessageSquareShare, Pencil, Plus, Radio, Trash2, UsersRound } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { showErrorToast } from "@/api/client";
import { getCharacters } from "@/api/characters";
import { createChatGroup, deleteChatGroup, listChatGroups, updateChatGroup } from "@/api/chatGroups";
import { listModelProviders } from "@/api/providers";
import type { CharacterRead } from "@/api/types/catalog";
import type { ChatGroupPayload, ChatGroupRead, ChatGroupUpdatePayload } from "@/api/types/chat-groups";
import type { ModelProviderRead } from "@/api/types/providers";
import { PopupSelect } from "@/components/composes/PopupSelect";
import { useConfirmDialog } from "@/components/composes/useConfirmDialog";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { resolveActualId } from "@/api/id-map";

type DialogMode = "create" | "edit";

type GroupFormState = {
  name: string;
  character_id: string;
  selected_model_id: string;
  default_temperature: string;
  max_context_messages: string;
  auto_compaction_enabled: boolean;
};

const EMPTY_FORM: GroupFormState = {
  name: "",
  character_id: "",
  selected_model_id: "",
  default_temperature: "0.7",
  max_context_messages: "24",
  auto_compaction_enabled: true,
};

function parseOptionalNumber(value: string) {
  const normalized = value.trim();
  return normalized ? Number(normalized) : null;
}

function formatTime(value: string) {
  return new Date(value).toLocaleString();
}

function buildModelOptions(providers: ModelProviderRead[]) {
  return providers.flatMap((provider) =>
    provider.available_models.map((model) => ({
      id: String(model.id),
      label: `${provider.name} / ${model.model_name}`,
    })),
  );
}

export default function ChatGroupsPage() {
  const { t } = useTranslation(["chatGroups", "common", "cocoons"]);
  const navigate = useNavigate();
  const [rooms, setRooms] = useState<ChatGroupRead[]>([]);
  const [characters, setCharacters] = useState<CharacterRead[]>([]);
  const [providers, setProviders] = useState<ModelProviderRead[]>([]);
  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<DialogMode>("create");
  const [isSaving, setIsSaving] = useState(false);
  const [form, setForm] = useState<GroupFormState>(EMPTY_FORM);
  const { confirm, confirmDialog } = useConfirmDialog();

  const modelOptions = useMemo(() => buildModelOptions(providers), [providers]);
  const characterOptions = useMemo(
    () =>
      characters.map((character) => ({
        value: String(character.id),
        label: character.name,
        description: character.description || `#${character.id}`,
        keywords: [String(character.id)],
      })),
    [characters],
  );
  const modelSelectOptions = useMemo(
    () =>
      modelOptions.map((model) => ({
        value: model.id,
        label: model.label,
        keywords: [model.id],
      })),
    [modelOptions],
  );
  const selectedRoom = useMemo(
    () => rooms.find((item) => item.id === selectedRoomId) || null,
    [rooms, selectedRoomId],
  );
  const selectedCharacter = useMemo(
    () => characters.find((item) => resolveActualId("character", item.id) === selectedRoom?.character_id) || null,
    [characters, selectedRoom],
  );
  const selectedModelLabel = useMemo(() => {
    const matched = modelOptions.find((item) => resolveActualId("model", item.id) === selectedRoom?.selected_model_id);
    return matched?.label || t("chatGroups:unknownModel");
  }, [modelOptions, selectedRoom, t]);

  useEffect(() => {
    void loadPage();
  }, []);

  async function loadPage() {
    setIsLoading(true);
    try {
      const [nextRooms, characterResponse, providerResponse] = await Promise.all([
        listChatGroups(),
        getCharacters(1, 100, "all"),
        listModelProviders(1, 100),
      ]);
      setRooms(nextRooms);
      setCharacters(characterResponse.items);
      setProviders(providerResponse.items);
      setSelectedRoomId((prev) => (prev && nextRooms.some((item) => item.id === prev) ? prev : nextRooms[0]?.id ?? null));
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("chatGroups:loadFailed"));
    } finally {
      setIsLoading(false);
    }
  }

  function openCreateDialog() {
    setDialogMode("create");
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEditDialog() {
    if (!selectedRoom) {
      return;
    }
    const matchingCharacter =
      characters.find((item) => resolveActualId("character", item.id) === selectedRoom.character_id) || null;
    const matchingModel =
      modelOptions.find((item) => resolveActualId("model", item.id) === selectedRoom.selected_model_id) || null;
    setDialogMode("edit");
    setForm({
      name: selectedRoom.name,
      character_id: matchingCharacter ? String(matchingCharacter.id) : "",
      selected_model_id: matchingModel?.id || "",
      default_temperature: String(selectedRoom.default_temperature),
      max_context_messages: String(selectedRoom.max_context_messages),
      auto_compaction_enabled: selectedRoom.auto_compaction_enabled,
    });
    setDialogOpen(true);
  }

  async function handleSave() {
    if (!form.name.trim() || !form.character_id || !form.selected_model_id) {
      return;
    }

    setIsSaving(true);
    try {
      if (dialogMode === "create") {
        const payload: ChatGroupPayload = {
          name: form.name.trim(),
          character_id: Number(form.character_id),
          selected_model_id: Number(form.selected_model_id),
          default_temperature: parseOptionalNumber(form.default_temperature),
          max_context_messages: parseOptionalNumber(form.max_context_messages),
          auto_compaction_enabled: form.auto_compaction_enabled,
        };
        const created = await createChatGroup(payload);
        toast.success(t("chatGroups:created"));
        setDialogOpen(false);
        await loadPage();
        setSelectedRoomId(created.id);
      } else if (selectedRoom) {
        const payload: ChatGroupUpdatePayload = {
          name: form.name.trim(),
          character_id: Number(form.character_id),
          selected_model_id: Number(form.selected_model_id),
          default_temperature: parseOptionalNumber(form.default_temperature),
          max_context_messages: parseOptionalNumber(form.max_context_messages),
          auto_compaction_enabled: form.auto_compaction_enabled,
        };
        await updateChatGroup(selectedRoom.id, payload);
        toast.success(t("chatGroups:updated"));
        setDialogOpen(false);
        await loadPage();
        setSelectedRoomId(selectedRoom.id);
      }
    } catch (error) {
      console.error(error);
      showErrorToast(error, dialogMode === "create" ? t("chatGroups:createFailed") : t("chatGroups:updateFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete() {
    if (!selectedRoom) {
      return;
    }
    const accepted = await confirm({
      title: t("common:delete"),
      description: t("chatGroups:deleteConfirm", { name: selectedRoom.name }),
      confirmLabel: t("common:delete"),
      cancelLabel: t("common:cancel"),
      variant: "destructive",
    });
    if (!accepted) {
      return;
    }
    try {
      await deleteChatGroup(selectedRoom.id);
      toast.success(t("chatGroups:deleted"));
      await loadPage();
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("chatGroups:deleteFailed"));
    }
  }

  return (
    <PageFrame
      title={t("chatGroups:title")}
      description={t("chatGroups:description")}
      actions={
        <>
          <Button variant="outline" onClick={loadPage}>
            {t("chatGroups:refreshRooms")}
          </Button>
          <Button onClick={openCreateDialog}>
            <Plus className="mr-2 size-4" />
            {t("chatGroups:newRoom")}
          </Button>
        </>
      }
    >
      {confirmDialog}
      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <Card className="overflow-hidden border-border/70 bg-card/90">
          <div className="border-b border-border/70">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquareShare className="size-4 text-orange-500" />
                {t("chatGroups:listTitle")}
              </CardTitle>
              <CardDescription>{t("chatGroups:listDescription")}</CardDescription>
            </CardHeader>
          </div>
          <CardContent className="space-y-3 p-4">
            {isLoading ? (
              <div className="rounded-3xl border border-dashed border-border/70 px-5 py-8 text-sm text-muted-foreground">
                {t("chatGroups:loadingRooms")}
              </div>
            ) : rooms.length === 0 ? (
              <div className="rounded-3xl border border-dashed border-border/70 px-5 py-8 text-sm text-muted-foreground">
                {t("chatGroups:emptyRooms")}
              </div>
            ) : (
              rooms.map((room) => {
                const character =
                  characters.find((item) => resolveActualId("character", item.id) === room.character_id) || null;
                const active = room.id === selectedRoomId;
                return (
                  <button
                    key={room.id}
                    type="button"
                    onClick={() => setSelectedRoomId(room.id)}
                    className={`w-full rounded-[28px] border p-4 text-left transition ${
                      active
                        ? "border-orange-400/40 bg-orange-500/8 shadow-sm"
                        : "border-border/70 bg-background/70 hover:border-orange-300/30 hover:bg-accent/20"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-base font-semibold">{room.name}</div>
                        <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                          <Badge variant="outline">{character?.name || t("chatGroups:unknownCharacter")}</Badge>
                          <Badge variant="outline">{t("chatGroups:turns", { count: room.max_context_messages })}</Badge>
                          {room.external_platform ? <Badge variant="secondary">{room.external_platform}</Badge> : null}
                        </div>
                      </div>
                      <Radio className={`size-4 ${active ? "text-orange-500" : "text-muted-foreground"}`} />
                    </div>
                    <div className="mt-3 text-xs text-muted-foreground">
                      {t("chatGroups:createdAt", { value: formatTime(room.created_at) })}
                    </div>
                  </button>
                );
              })
            )}
          </CardContent>
        </Card>

        <Card className="border-border/70 bg-card/90">
          <div className="border-b border-border/70 bg-linear-to-br from-cyan-500/10 via-transparent to-amber-500/10">
            <CardHeader>
              <CardTitle>{t("chatGroups:previewTitle")}</CardTitle>
              <CardDescription>{t("chatGroups:previewDescription")}</CardDescription>
            </CardHeader>
          </div>
          <CardContent className="space-y-4 p-4">
            {selectedRoom ? (
              <>
                <div className="rounded-[28px] border border-border/70 bg-background/70 p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="text-xl font-semibold">{selectedRoom.name}</div>
                      <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                        <Badge variant="secondary">{t("chatGroups:singleAiRoom")}</Badge>
                        <Badge variant="outline">{selectedCharacter?.name || t("chatGroups:unknownCharacter")}</Badge>
                        <Badge variant="outline">{selectedModelLabel}</Badge>
                      </div>
                    </div>
                    <Button onClick={() => navigate(`/chat-groups/${selectedRoom.id}`)}>
                      {t("chatGroups:openWorkspace")}
                      <ArrowRight className="ml-2 size-4" />
                    </Button>
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-[24px] border border-border/70 p-4">
                    <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("chatGroups:contextWindow")}</div>
                    <div className="mt-2 text-base font-semibold">{t("chatGroups:messagesCount", { count: selectedRoom.max_context_messages })}</div>
                  </div>
                  <div className="rounded-[24px] border border-border/70 p-4">
                    <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("chatGroups:temperature")}</div>
                    <div className="mt-2 text-base font-semibold">{selectedRoom.default_temperature.toFixed(1)}</div>
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-[24px] border border-border/70 p-4">
                    <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("chatGroups:compaction")}</div>
                    <div className="mt-2 text-base font-semibold">
                      {selectedRoom.auto_compaction_enabled ? t("chatGroups:compactionAuto") : t("chatGroups:compactionManual")}
                    </div>
                  </div>
                  <div className="rounded-[24px] border border-border/70 p-4">
                    <div className="text-xs uppercase tracking-wide text-muted-foreground">{t("chatGroups:roomType")}</div>
                    <div className="mt-2 text-base font-semibold">
                      {t("chatGroups:roomTypeShared")}
                    </div>
                  </div>
                </div>

                <div className="rounded-[24px] border border-dashed border-border/70 bg-background/50 p-4 text-sm text-muted-foreground">
                  {t("chatGroups:workspaceHint")}
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" onClick={openEditDialog}>
                    <Pencil className="mr-2 size-4" />
                    {t("chatGroups:editRoom")}
                  </Button>
                  <Button variant="outline" onClick={() => navigate(`/chat-groups/${selectedRoom.id}`)}>
                    <UsersRound className="mr-2 size-4" />
                    {t("chatGroups:manageMembers")}
                  </Button>
                  <Button variant="destructive" onClick={handleDelete}>
                    <Trash2 className="mr-2 size-4" />
                    {t("chatGroups:deleteRoom")}
                  </Button>
                </div>
              </>
            ) : (
              <div className="rounded-[28px] border border-dashed border-border/70 px-5 py-8 text-sm text-muted-foreground">
                {t("chatGroups:emptySelection")}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>{dialogMode === "create" ? t("chatGroups:dialogCreateTitle") : t("chatGroups:dialogEditTitle")}</DialogTitle>
            <DialogDescription>{t("chatGroups:dialogDescription")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>{t("common:name")}</Label>
              <Input value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t("chatGroups:characterFieldLabel")}</Label>
                <PopupSelect
                  title={t("chatGroups:selectCharacter")}
                  description={t("chatGroups:dialogDescription")}
                  placeholder={t("chatGroups:selectCharacter")}
                  searchPlaceholder={t("common:search")}
                  emptyText={t("chatGroups:emptyRooms")}
                  value={form.character_id}
                  onValueChange={(value) => setForm((prev) => ({ ...prev, character_id: value }))}
                  options={characterOptions}
                />
              </div>
              <div className="grid gap-2">
                <Label>{t("common:model")}</Label>
                <PopupSelect
                  title={t("common:selectModel")}
                  description={t("chatGroups:dialogDescription")}
                  placeholder={t("common:selectModel")}
                  searchPlaceholder={t("common:search")}
                  emptyText={t("chatGroups:emptyRooms")}
                  value={form.selected_model_id}
                  onValueChange={(value) => setForm((prev) => ({ ...prev, selected_model_id: value }))}
                  options={modelSelectOptions}
                />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t("chatGroups:temperature")}</Label>
                <Input
                  value={form.default_temperature}
                  onChange={(event) => setForm((prev) => ({ ...prev, default_temperature: event.target.value }))}
                />
              </div>
              <div className="grid gap-2">
                <Label>{t("cocoons:maxContextMessages")}</Label>
                <Input
                  value={form.max_context_messages}
                  onChange={(event) => setForm((prev) => ({ ...prev, max_context_messages: event.target.value }))}
                />
              </div>
            </div>
            <label className="flex items-center gap-3 rounded-2xl border border-border/70 bg-background/50 px-4 py-3 text-sm">
              <Checkbox
                checked={form.auto_compaction_enabled}
                onCheckedChange={(checked) =>
                  setForm((prev) => ({ ...prev, auto_compaction_enabled: Boolean(checked) }))
                }
              />
              {t("chatGroups:autoCompactionLabel")}
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {t("common:cancel")}
            </Button>
            <Button disabled={isSaving || !form.name.trim() || !form.character_id || !form.selected_model_id} onClick={handleSave}>
              {isSaving ? t("common:saving") : dialogMode === "create" ? t("chatGroups:newRoom") : t("common:saveChanges")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageFrame>
  );
}
