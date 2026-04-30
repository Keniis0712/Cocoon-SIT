import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { compactCocoonContext, getCocoon, getCocoonMessages, getCocoonSessionState, retryCocoonReply, sendCocoonMessage, updateCocoon } from "@/api/cocoons";
import { localizeApiMessage, showErrorToast } from "@/api/client";
import { listModelProviders } from "@/api/providers";
import { getSystemSettings } from "@/api/settings";
import { bindCocoonTags, listTags } from "@/api/tags";
import type { TagRead } from "@/api/types/catalog";
import type { MessageRead } from "@/api/types/chat";
import type { CocoonRead } from "@/api/types/cocoons";
import type { AvailableModelRead } from "@/api/types/providers";
import type { WakeupTaskRead } from "@/api/types/wakeups";
import { listCocoonWakeups } from "@/api/wakeups";
import { createRuntimeWsEventHandler } from "@/features/workspace/runtimeWsEvents";
import { useWorkspaceMessagingController } from "@/features/workspace/useWorkspaceMessagingController";
import { useCocoonWs } from "@/hooks/useCocoonWs";
import { useUserStore } from "@/store/useUserStore";

type CocoonWorkspaceController = {
  selectedCocoon: CocoonRead | null;
  providerModels: AvailableModelRead[];
  availableTags: TagRead[];
  availableAddableTags: TagRead[];
  selectedTagIds: number[];
  messageInput: string;
  currentAiWakeup: WakeupTaskRead | null;
  isLoading: boolean;
  isLoadingMore: boolean;
  isSending: boolean;
  hasMore: boolean;
  isCompacting: boolean;
  isUpdatingTags: boolean;
  addTagValue: string;
  session: ReturnType<typeof useWorkspaceMessagingController>["session"];
  visibleMessages: MessageRead[];
  viewportRef: ReturnType<typeof useWorkspaceMessagingController>["viewportRef"];
  onMessageInputChange: (value: string) => void;
  handleSendMessage: () => Promise<void>;
  loadOlderMessages: () => Promise<void>;
  handleChangeModel: (modelId: string) => Promise<void>;
  handleRetryReply: () => Promise<void>;
  handleCompactContext: () => Promise<void>;
  handleAddTag: (value: string) => Promise<void>;
  persistTagIds: (nextTagIds: number[]) => Promise<void>;
  loadWorkspace: (initial?: boolean) => Promise<void>;
};

function sortMessages(items: MessageRead[]) {
  return [...items].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime() || a.id - b.id,
  );
}

export function useCocoonWorkspaceController(cocoonId: number): CocoonWorkspaceController {
  const { t } = useTranslation("workspace");
  const navigate = useNavigate();
  const currentUser = useUserStore((state) => state.userInfo);
  const canManageSystem = Boolean(currentUser?.can_manage_system);

  const [selectedCocoon, setSelectedCocoon] = useState<CocoonRead | null>(null);
  const [providerModels, setProviderModels] = useState<AvailableModelRead[]>([]);
  const [availableTags, setAvailableTags] = useState<TagRead[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [currentAiWakeup, setCurrentAiWakeup] = useState<WakeupTaskRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [isCompacting, setIsCompacting] = useState(false);
  const [isUpdatingTags, setIsUpdatingTags] = useState(false);
  const [addTagValue, setAddTagValue] = useState("__add");

  const messaging = useWorkspaceMessagingController({
    sessionKey: cocoonId,
    isLoading,
    timezone: currentUser?.timezone || "UTC",
    sendMessage: (payload) => sendCocoonMessage(cocoonId, payload),
  });

  const availableAddableTags = useMemo(
    () => availableTags.filter((tag) => !tag.is_system && !selectedTagIds.includes(tag.id)),
    [availableTags, selectedTagIds],
  );

  useEffect(() => {
    if (!Number.isFinite(cocoonId) || cocoonId <= 0) {
      toast.error(t("invalidId"));
      navigate("/cocoons", { replace: true });
      return;
    }

    messaging.resetRuntimeSession();
    void loadWorkspace(true);
  }, [canManageSystem, cocoonId]);

  const handleSocketEvent = createRuntimeWsEventHandler({
    sessionKey: cocoonId,
    upsertMessage: messaging.upsertMessage,
    setStreamingAssistant: messaging.setStreamingAssistant,
    appendStreamingAssistant: messaging.appendStreamingAssistant,
    applyStatePatch: messaging.applyStatePatch,
    setError: messaging.setError,
    reloadWorkspace: () => {
      void loadWorkspace(false);
    },
    reloadWakeups: () => {
      void loadCurrentAiWakeup();
    },
    scrollToBottom: messaging.scrollToBottom,
    onRoundFailed: (detail) => {
      toast.error(t("aiRequestFailed", { detail: localizeApiMessage(detail) }));
    },
  });

  useCocoonWs({
    cocoonId,
    enabled: Number.isFinite(cocoonId) && cocoonId > 0,
    onEvent: handleSocketEvent,
    onRecover: async () => {
      await loadWorkspace(false);
      toast.success(t("realtimeRestored"));
    },
    onError: (message) => {
      messaging.setError(cocoonId, localizeApiMessage(message));
    },
  });

  async function loadWorkspace(initial = false) {
    if (initial) {
      setIsLoading(true);
    }
    try {
      const [cocoon, sessionState, messageResponse, providerResponse, tagItems, wakeups, settings] = await Promise.all([
        getCocoon(cocoonId),
        getCocoonSessionState(cocoonId),
        getCocoonMessages(cocoonId, null, 50),
        listModelProviders(1, 100),
        listTags(),
        listCocoonWakeups(cocoonId, { status: "queued", only_ai: true, limit: 1 }),
        canManageSystem ? getSystemSettings().catch(() => null) : Promise.resolve(null),
      ]);
      const provider = providerResponse.items.find((item) => item.id === cocoon.provider_id) || null;
      const nextAllowedModelIds =
        canManageSystem && settings?.allowed_model_ids?.length ? new Set<number>(settings.allowed_model_ids) : null;
      setSelectedCocoon(cocoon);
      setProviderModels(
        nextAllowedModelIds && provider
          ? provider.available_models.filter((model) => nextAllowedModelIds.has(model.id))
          : provider?.available_models || [],
      );
      setAvailableTags(tagItems);
      setSelectedTagIds(
        (cocoon.tags || []).filter((item) => !item.is_system).map((item) => item.id),
      );
      setCurrentAiWakeup(wakeups[0] || null);
      messaging.setMessages(cocoonId, sortMessages(messageResponse.items));
      messaging.applyStatePatch(cocoonId, {
        relationScore: sessionState.relation_score,
        personaJson: sessionState.persona_json,
        activeTags: sessionState.active_tags,
        currentModelId: sessionState.current_model_id ?? cocoon.selected_model_id,
        currentWakeupTaskId: sessionState.current_wakeup_task_id,
        dispatchState: sessionState.dispatch_status || cocoon.dispatch_job?.status || cocoon.dispatch_status,
        dispatchReason: null,
        debounceUntil: sessionState.debounce_until,
      });
      setHasMore(Boolean(messageResponse.has_more));
      messaging.setError(cocoonId, null);
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("loadFailed"));
    } finally {
      setIsLoading(false);
    }
  }

  async function loadOlderMessages() {
    if (isLoadingMore || !messaging.visibleMessages.length) {
      return;
    }
    setIsLoadingMore(true);
    try {
      const oldestId = messaging.visibleMessages[0]?.id ?? null;
      const response = await getCocoonMessages(cocoonId, oldestId, 50);
      messaging.prependMessages(cocoonId, sortMessages(response.items));
      setHasMore(Boolean(response.has_more));
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("olderMessagesLoadFailed"));
    } finally {
      setIsLoadingMore(false);
    }
  }

  async function handleChangeModel(modelId: string) {
    if (!selectedCocoon) {
      return;
    }
    try {
      const updated = await updateCocoon(selectedCocoon.id, { selected_model_id: Number(modelId) });
      setSelectedCocoon(updated);
      messaging.applyStatePatch(cocoonId, { currentModelId: updated.selected_model_id });
      toast.success(t("modelUpdated"));
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("switchModelFailed"));
    }
  }

  async function loadCurrentAiWakeup() {
    try {
      const wakeups = await listCocoonWakeups(cocoonId, { status: "queued", only_ai: true, limit: 1 });
      setCurrentAiWakeup(wakeups[0] || null);
    } catch (error) {
      console.error(error);
    }
  }

  async function handleRetryReply() {
    try {
      messaging.setStreamingAssistant(cocoonId, "");
      await retryCocoonReply(cocoonId, (event) => {
        if (event.type === "chunk") {
          messaging.appendStreamingAssistant(cocoonId, event.delta);
        }
        if (event.type === "done" && event.assistant_message) {
          messaging.upsertMessage(cocoonId, event.assistant_message);
          messaging.setStreamingAssistant(cocoonId, "");
        }
        if (event.type === "error") {
          messaging.setStreamingAssistant(cocoonId, "");
          toast.error(localizeApiMessage(event.detail));
        }
      });
    } catch (error) {
      showErrorToast(error, t("retryReplyFailed"));
    }
  }

  async function handleCompactContext() {
    if (!selectedCocoon || isCompacting) {
      return;
    }
    setIsCompacting(true);
    try {
      const result = await compactCocoonContext(cocoonId, { mode: "manual" });
      toast.success(t("compactQueued", { status: result.status }));
      await loadWorkspace(false);
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("compactFailed"));
    } finally {
      setIsCompacting(false);
    }
  }

  async function persistTagIds(nextTagIds: number[]) {
    if (!selectedCocoon || isUpdatingTags) {
      return;
    }
    const normalized = Array.from(new Set(nextTagIds)).sort((a, b) => a - b);
    const previousIds = selectedTagIds;
    setIsUpdatingTags(true);
    setSelectedTagIds(normalized);
    try {
      const tags = await bindCocoonTags(selectedCocoon.id, normalized);
      setSelectedCocoon((prev) => (prev ? { ...prev, tags } : prev));
      messaging.applyStatePatch(cocoonId, { activeTags: tags.map((item) => item.actual_id) });
    } catch (error) {
      setSelectedTagIds(previousIds);
      console.error(error);
      showErrorToast(error, t("updateTagsFailed"));
    } finally {
      setIsUpdatingTags(false);
      setAddTagValue("__add");
    }
  }

  async function handleAddTag(value: string) {
    setAddTagValue(value);
    if (value === "__add") {
      return;
    }
    const tagId = Number(value);
    if (!Number.isFinite(tagId)) {
      setAddTagValue("__add");
      return;
    }
    await persistTagIds([...selectedTagIds, tagId]);
  }

  return {
    selectedCocoon,
    providerModels,
    availableTags,
    availableAddableTags,
    selectedTagIds,
    messageInput: messaging.messageInput,
    currentAiWakeup,
    isLoading,
    isLoadingMore,
    isSending: messaging.isSending,
    hasMore,
    isCompacting,
    isUpdatingTags,
    addTagValue,
    session: messaging.session,
    visibleMessages: messaging.visibleMessages,
    viewportRef: messaging.viewportRef,
    onMessageInputChange: messaging.onMessageInputChange,
    handleSendMessage: messaging.handleSendMessage,
    loadOlderMessages,
    handleChangeModel,
    handleRetryReply,
    handleCompactContext,
    handleAddTag,
    persistTagIds,
    loadWorkspace,
  };
}
