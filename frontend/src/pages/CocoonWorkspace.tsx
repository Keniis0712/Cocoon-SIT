import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ChevronUp, Loader2, MemoryStick, Plus, RefreshCcw } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { showErrorToast } from "@/api/client";
import { compactCocoonContext, getCocoon, getCocoonMessages, getCocoonSessionState, retryCocoonReply, sendCocoonMessage, updateCocoon } from "@/api/cocoons";
import { listModelProviders } from "@/api/providers";
import { bindCocoonTags, listTags } from "@/api/tags";
import type { TagRead } from "@/api/types/catalog";
import type { CocoonRead } from "@/api/types/cocoons";
import type { MessageRead } from "@/api/types/chat";
import type { AvailableModelRead } from "@/api/types/providers";
import type { WakeupTaskRead } from "@/api/types/wakeups";
import { listCocoonWakeups } from "@/api/wakeups";
import PageFrame from "@/components/PageFrame";
import { Button } from "@/components/ui/button";
import { CocoonConversationPanel } from "@/features/cocoons/components/CocoonConversationPanel";
import { CocoonSessionPanel } from "@/features/cocoons/components/CocoonSessionPanel";
import { createRuntimeWsEventHandler } from "@/features/workspace/runtimeWsEvents";
import { useCocoonWs } from "@/hooks/useCocoonWs";
import { useChatSessionStore } from "@/store/useChatSessionStore";

function getVisibleMessages(items: MessageRead[]) {
  return items.filter((item) => !item.is_thought);
}

export default function CocoonWorkspacePage() {
  const navigate = useNavigate();
  const params = useParams();
  const cocoonId = Number(params.cocoonId);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const typingStartedAtRef = useRef<number | null>(null);
  const hasAutoScrolledRef = useRef(false);

  const [selectedCocoon, setSelectedCocoon] = useState<CocoonRead | null>(null);
  const [providerModels, setProviderModels] = useState<AvailableModelRead[]>([]);
  const [availableTags, setAvailableTags] = useState<TagRead[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [messageInput, setMessageInput] = useState("");
  const [currentAiWakeup, setCurrentAiWakeup] = useState<WakeupTaskRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [isCompacting, setIsCompacting] = useState(false);
  const [isUpdatingTags, setIsUpdatingTags] = useState(false);
  const [addTagValue, setAddTagValue] = useState("__add");

  const session = useChatSessionStore((state) => state.sessions[cocoonId] ?? null);
  const ensureSession = useChatSessionStore((state) => state.ensureSession);
  const resetSession = useChatSessionStore((state) => state.resetSession);
  const setMessages = useChatSessionStore((state) => state.setMessages);
  const prependMessages = useChatSessionStore((state) => state.prependMessages);
  const upsertMessage = useChatSessionStore((state) => state.upsertMessage);
  const setStreamingAssistant = useChatSessionStore((state) => state.setStreamingAssistant);
  const appendStreamingAssistant = useChatSessionStore((state) => state.appendStreamingAssistant);
  const applyStatePatch = useChatSessionStore((state) => state.applyStatePatch);
  const setTyping = useChatSessionStore((state) => state.setTyping);
  const setError = useChatSessionStore((state) => state.setError);

  const visibleMessages = useMemo(() => getVisibleMessages(session?.messages || []), [session?.messages]);
  const availableAddableTags = useMemo(
    () => availableTags.filter((tag) => !selectedTagIds.includes(tag.id)),
    [availableTags, selectedTagIds],
  );

  useEffect(() => {
    if (!Number.isFinite(cocoonId) || cocoonId <= 0) {
      toast.error("Invalid cocoon id");
      navigate("/cocoons", { replace: true });
      return;
    }

    ensureSession(cocoonId);
    resetSession(cocoonId);
    hasAutoScrolledRef.current = false;
    void loadWorkspace(true);
  }, [cocoonId]);

  const handleSocketEvent = createRuntimeWsEventHandler({
    sessionKey: cocoonId,
    upsertMessage,
    setStreamingAssistant,
    appendStreamingAssistant,
    applyStatePatch,
    setError,
    reloadWorkspace: () => {
      void loadWorkspace(false);
    },
    reloadWakeups: () => {
      void loadCurrentAiWakeup();
    },
    scrollToBottom: () => {
      if (viewportRef.current) {
        viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
      }
    },
    onRoundFailed: (detail) => {
      toast.error(`AI request failed: ${detail}`);
    },
  });

  useCocoonWs({
    cocoonId,
    enabled: Number.isFinite(cocoonId) && cocoonId > 0,
    onEvent: handleSocketEvent,
    onRecover: async () => {
      await loadWorkspace(false);
      toast.success("Realtime connection restored");
    },
    onError: (message) => {
      setError(cocoonId, message);
    },
  });

  useEffect(() => {
    if (!viewportRef.current) return;
    if (!hasAutoScrolledRef.current) {
      viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
      hasAutoScrolledRef.current = true;
    }
  }, [visibleMessages.length]);

  async function loadWorkspace(initial = false) {
    if (initial) {
      setIsLoading(true);
    }
    try {
      const [cocoon, sessionState, messageResponse, providerResponse, tagItems, wakeups] = await Promise.all([
        getCocoon(cocoonId),
        getCocoonSessionState(cocoonId),
        getCocoonMessages(cocoonId, null, 50),
        listModelProviders(1, 100),
        listTags(),
        listCocoonWakeups(cocoonId, { status: "queued", only_ai: true, limit: 1 }),
      ]);
      const provider =
        providerResponse.items.find((item: { id: number }) => item.id === cocoon.provider_id) || null;
      const sortedMessages = [...messageResponse.items].sort(
        (a: { created_at: string; id: number }, b: { created_at: string; id: number }) =>
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime() || a.id - b.id,
      );
      setSelectedCocoon(cocoon);
      setProviderModels(provider?.available_models || []);
      setAvailableTags(tagItems);
      setSelectedTagIds((cocoon.tags || []).map((item: { id: number }) => item.id));
      setCurrentAiWakeup(wakeups[0] || null);
      setMessages(cocoonId, sortedMessages);
      applyStatePatch(cocoonId, {
        relationScore: sessionState.relation_score,
        personaJson: sessionState.persona_json,
        activeTags: sessionState.active_tags,
        currentModelId: sessionState.current_model_id ?? cocoon.selected_model_id,
        currentWakeupTaskId: sessionState.current_wakeup_task_id,
        dispatchState: sessionState.dispatch_status || cocoon.dispatch_job?.status || cocoon.dispatch_status,
        dispatchReason: null,
        debounceUntil: sessionState.debounce_until,
      });
      setHasMore(sortedMessages.length < messageResponse.total);
      setError(cocoonId, null);
    } catch (error) {
      console.error(error);
      showErrorToast(error, "Failed to load workspace");
    } finally {
      setIsLoading(false);
    }
  }

  async function loadOlderMessages() {
    if (isLoadingMore || !visibleMessages.length) return;
    setIsLoadingMore(true);
    try {
      const oldestId = visibleMessages[0]?.id ?? null;
      const response = await getCocoonMessages(cocoonId, oldestId, 50);
      const sortedMessages = [...response.items].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime() || a.id - b.id);
      prependMessages(cocoonId, sortedMessages);
      setHasMore((session?.messages.length || 0) + sortedMessages.length < response.total);
    } catch (error) {
      console.error(error);
      showErrorToast(error, "Failed to load older messages");
    } finally {
      setIsLoadingMore(false);
    }
  }

  async function handleSendMessage() {
    if (!messageInput.trim() || isSending) return;
    const content = messageInput.trim();
    const now = Date.now();
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || null;
    const locale = navigator.language || null;
    const lastMessageAt = visibleMessages.length ? new Date(visibleMessages[visibleMessages.length - 1].created_at).getTime() : null;
    const typingHint = typingStartedAtRef.current ? Math.max(0, now - typingStartedAtRef.current) : null;
    const idleSeconds = lastMessageAt ? Math.max(0, Math.floor((now - lastMessageAt) / 1000)) : null;
    const recentTurnCount = visibleMessages.slice(-8).length;

    setIsSending(true);
    setTyping(cocoonId, false);
    setError(cocoonId, null);
    try {
      const result = await sendCocoonMessage(cocoonId, {
        content,
        client_request_id: window.crypto?.randomUUID?.() || `${Date.now()}`,
        client_sent_at: new Date(now).toISOString(),
        timezone,
        locale,
        idle_seconds: idleSeconds,
        recent_turn_count: recentTurnCount,
        typing_hint_ms: typingHint,
      });
      upsertMessage(cocoonId, result.user_message);
      applyStatePatch(cocoonId, {
        dispatchState: result.dispatch_status,
        dispatchReason: null,
        debounceUntil: result.debounce_until,
      });
      setMessageInput("");
      typingStartedAtRef.current = null;
      queueMicrotask(() => {
        if (viewportRef.current) {
          viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
        }
      });
    } catch (error) {
      console.error(error);
      showErrorToast(error, "Failed to send message");
    } finally {
      setIsSending(false);
    }
  }

  async function handleChangeModel(modelId: string) {
    if (!selectedCocoon) return;
    try {
      const updated = await updateCocoon(selectedCocoon.id, { selected_model_id: Number(modelId) });
      setSelectedCocoon(updated);
      applyStatePatch(cocoonId, { currentModelId: updated.selected_model_id });
      toast.success("Model updated");
    } catch (error) {
      console.error(error);
      showErrorToast(error, "Failed to switch model");
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
      setStreamingAssistant(cocoonId, "");
      await retryCocoonReply(cocoonId, (event) => {
        if (event.type === "chunk") {
          appendStreamingAssistant(cocoonId, event.delta);
        }
        if (event.type === "done" && event.assistant_message) {
          upsertMessage(cocoonId, event.assistant_message);
          setStreamingAssistant(cocoonId, "");
        }
        if (event.type === "error") {
          setStreamingAssistant(cocoonId, "");
          toast.error(event.detail);
        }
      });
    } catch (error) {
      showErrorToast(error, "Failed to retry reply");
    }
  }

  async function handleCompactContext() {
    if (!selectedCocoon || isCompacting) return;
    setIsCompacting(true);
    try {
      const result = await compactCocoonContext(cocoonId, { mode: "manual" });
      toast.success(`Compaction job queued: ${result.status}`);
      await loadWorkspace(false);
    } catch (error) {
      console.error(error);
      showErrorToast(error, "Failed to compact context");
    } finally {
      setIsCompacting(false);
    }
  }

  async function persistTagIds(nextTagIds: number[]) {
    if (!selectedCocoon || isUpdatingTags) return;
    const normalized = Array.from(new Set(nextTagIds)).sort((a, b) => a - b);
    const previousIds = selectedTagIds;
    setIsUpdatingTags(true);
    setSelectedTagIds(normalized);
    try {
      const tags = await bindCocoonTags(selectedCocoon.id, normalized);
      setSelectedCocoon((prev) => (prev ? { ...prev, tags } : prev));
      applyStatePatch(cocoonId, { activeTags: tags.map((item: { name: string }) => item.name) });
    } catch (error) {
      setSelectedTagIds(previousIds);
      console.error(error);
      showErrorToast(error, "Failed to update chat tags");
    } finally {
      setIsUpdatingTags(false);
      setAddTagValue("__add");
    }
  }

  async function handleAddTag(value: string) {
    setAddTagValue(value);
    if (value === "__add") return;
    const tagId = Number(value);
    if (!Number.isFinite(tagId)) {
      setAddTagValue("__add");
      return;
    }
    await persistTagIds([...selectedTagIds, tagId]);
  }

  return (
    <PageFrame
      title={selectedCocoon?.name || "Chat"}
      actions={
        <>
          <Button variant="outline" onClick={() => navigate("/cocoons")}>
            <ArrowLeft className="mr-2 size-4" />
            Back to Cocoons
          </Button>
          <Button variant="outline" onClick={() => navigate(`/cocoons/${cocoonId}/memories`)}>
            <MemoryStick className="mr-2 size-4" />
            Memories
          </Button>
          <Button variant="outline" onClick={handleCompactContext} disabled={isCompacting || isLoading}>
            {isCompacting ? <Loader2 className="mr-2 size-4 animate-spin" /> : <RefreshCcw className="mr-2 size-4" />}
            Compress Context
          </Button>
          <Button variant="outline" onClick={handleRetryReply}>
            <RefreshCcw className="mr-2 size-4" />
            Retry Last Reply
          </Button>
        </>
      }
    >
      <div className="grid gap-4 xl:grid-cols-[1.7fr_0.95fr]">
        <CocoonConversationPanel
          viewportRef={viewportRef}
          isLoading={isLoading}
          hasMore={hasMore}
          isLoadingMore={isLoadingMore}
          visibleMessages={visibleMessages}
          streamingAssistant={session?.streamingAssistant || ""}
          messageInput={messageInput}
          isSending={isSending}
          onLoadOlderMessages={loadOlderMessages}
          onMessageInputChange={(value) => {
            if (!typingStartedAtRef.current) {
              typingStartedAtRef.current = Date.now();
            }
            setTyping(cocoonId, true);
            setMessageInput(value);
          }}
          onSendMessage={handleSendMessage}
        />

        <div className="order-2 space-y-4">
          <CocoonSessionPanel
            selectedCocoon={selectedCocoon}
            providerModels={providerModels}
            sessionActiveTags={session?.activeTags || []}
            selectedTagIds={selectedTagIds}
            availableAddableTags={availableAddableTags}
            addTagValue={addTagValue}
            isUpdatingTags={isUpdatingTags}
            currentModelId={session?.currentModelId}
            dispatchState={session?.dispatchState}
            relationScore={session?.relationScore}
            currentAiWakeup={currentAiWakeup}
            debounceUntil={session?.debounceUntil}
            dispatchReason={session?.dispatchReason}
            lastError={session?.lastError}
            onRemoveTag={(tagId) => void persistTagIds(selectedTagIds.filter((id) => id !== tagId))}
            onAddTag={(value) => void handleAddTag(value)}
            onChangeModel={handleChangeModel}
          />
        </div>
      </div>
    </PageFrame>
  );
}
