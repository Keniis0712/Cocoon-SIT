import { useEffect, useMemo, useRef, useState } from "react";
import { isAxiosError } from "axios";
import { ArrowLeft, ChevronUp, Loader2, MemoryStick, Plus, RefreshCcw } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { compactCocoonContext, getCocoon, getCocoonMessages, getCocoonSessionState, retryCocoonReply, sendCocoonMessage, updateCocoon } from "@/api/cocoons";
import { listModelProviders } from "@/api/providers";
import { bindCocoonTags, listTags } from "@/api/tags";
import type { AvailableModelRead, CocoonRead, MessageRead, RuntimeWsEvent, TagRead } from "@/api/types";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCocoonWs } from "@/hooks/useCocoonWs";
import { useChatSessionStore } from "@/store/useChatSessionStore";

function formatTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "-";
}

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

  function handleSocketEvent(event: RuntimeWsEvent) {
    if (event.type === "reply_started") {
      if ("user_message" in event && event.user_message) {
        upsertMessage(cocoonId, event.user_message);
      }
      setStreamingAssistant(cocoonId, "");
      applyStatePatch(cocoonId, { dispatchState: "running", dispatchReason: null });
      return;
    }
    if (event.type === "reply_chunk") {
      appendStreamingAssistant(cocoonId, event.delta);
      return;
    }
    if (event.type === "reply_done") {
      if ("assistant_message" in event && event.assistant_message) {
        upsertMessage(cocoonId, event.assistant_message);
      } else {
        void loadWorkspace(false);
      }
      setStreamingAssistant(cocoonId, "");
      applyStatePatch(cocoonId, { dispatchState: "idle", dispatchReason: null });
      queueMicrotask(() => {
        if (viewportRef.current) {
          viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
        }
      });
      return;
    }
    if (event.type === "state_patch") {
      applyStatePatch(cocoonId, {
        relationScore: event.relation_score,
        personaJson: event.persona_json,
        activeTags: event.active_tags,
        currentModelId: event.current_model_id,
        currentWakeupTaskId: event.current_wakeup_task_id ?? null,
        dispatchState: "idle",
        dispatchReason: null,
      });
      return;
    }
    if (event.type === "dispatch_queued") {
      applyStatePatch(cocoonId, {
        dispatchState: event.status || "queued",
        dispatchReason: event.reason ?? null,
        debounceUntil: event.debounce_until ?? null,
      });
      return;
    }
    if (event.type === "round_failed") {
      setStreamingAssistant(cocoonId, "");
      setError(cocoonId, event.error_detail);
      applyStatePatch(cocoonId, { dispatchState: "error" });
      toast.error(`AI request failed: ${event.error_detail}`);
    }
  }

  async function loadWorkspace(initial = false) {
    if (initial) {
      setIsLoading(true);
    }
    try {
      const [cocoon, sessionState, messageResponse, providerResponse, tagItems] = await Promise.all([
        getCocoon(cocoonId),
        getCocoonSessionState(cocoonId),
        getCocoonMessages(cocoonId, null, 50),
        listModelProviders(1, 100),
        listTags(),
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
      toast.error("Failed to load workspace");
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
      toast.error("Failed to load older messages");
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
      toast.error(error instanceof Error ? error.message : "Failed to send message");
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
      toast.error("Failed to switch model");
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
      if (isAxiosError(error)) {
        toast.error(String(error.response?.data?.detail || error.message));
      } else {
        toast.error("Failed to retry reply");
      }
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
      toast.error("Failed to compact context");
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
      toast.error("Failed to update chat tags");
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
      description="Chat only. Long-term memory has moved to its own page."
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
        <Card className="order-1 min-h-[78vh] border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle>Conversation</CardTitle>
            <CardDescription>Newest messages stay at the bottom. Load older messages upward.</CardDescription>
          </CardHeader>
          <CardContent className="flex h-[calc(78vh-5rem)] flex-col gap-4">
            <div ref={viewportRef} className="flex-1 overflow-auto rounded-[28px] border border-border/70 bg-background/60 p-4">
              {isLoading ? (
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Loading messages...</div>
              ) : (
                <div className="space-y-4">
                  {hasMore ? (
                    <div className="flex justify-center">
                      <Button variant="outline" size="sm" disabled={isLoadingMore} onClick={loadOlderMessages}>
                        {isLoadingMore ? <Loader2 className="mr-2 size-4 animate-spin" /> : <ChevronUp className="mr-2 size-4" />}
                        Load older messages
                      </Button>
                    </div>
                  ) : null}
                  {visibleMessages.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">No messages yet. Send one to start this branch.</div>
                  ) : null}
                  {visibleMessages.map((message) => {
                    const isUser = message.role === "user";
                    return (
                      <div key={message.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                        <div className={`max-w-[88%] rounded-[24px] border px-4 py-3 shadow-sm ${isUser ? "border-primary/30 bg-primary/10" : "border-border/70 bg-card"}`}>
                          <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                            <span>{isUser ? "User" : "Assistant"}</span>
                            <span>{formatTime(message.created_at)}</span>
                          </div>
                          <div className="whitespace-pre-wrap text-sm leading-6">{message.content}</div>
                        </div>
                      </div>
                    );
                  })}
                  {session?.streamingAssistant ? (
                    <div className="flex justify-start">
                      <div className="max-w-[88%] rounded-[24px] border border-dashed border-primary/40 bg-primary/5 px-4 py-3">
                        <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                          <span>Assistant</span>
                          <Badge variant="outline">Streaming</Badge>
                        </div>
                        <div className="whitespace-pre-wrap text-sm leading-6">{session.streamingAssistant}</div>
                      </div>
                    </div>
                  ) : null}
                </div>
              )}
            </div>

            <div className="rounded-[28px] border border-border/70 bg-background/70 p-3">
              <Textarea
                rows={4}
                placeholder="Type your next message..."
                value={messageInput}
                disabled={isSending || isLoading}
                onChange={(event) => {
                  if (!typingStartedAtRef.current) {
                    typingStartedAtRef.current = Date.now();
                  }
                  setTyping(cocoonId, true);
                  setMessageInput(event.target.value);
                }}
              />
              <div className="mt-3 flex items-center justify-between gap-2">
                <div />
                <Button disabled={!messageInput.trim() || isSending || isLoading} onClick={handleSendMessage}>
                  {isSending ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
                  Send
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="order-2 space-y-4">
        <Card className="border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle>Current Session</CardTitle>
            <CardDescription>Manage chat tags and switch the current model in place.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="mb-2 text-sm text-muted-foreground">Active Tags</div>
              <div className="flex flex-wrap gap-2">
                {(session?.activeTags?.length ? session.activeTags : selectedCocoon?.tags?.map((item) => item.name) || []).map((tag) => (
                  <Badge key={tag} variant="secondary">{tag}</Badge>
                ))}
                {!(session?.activeTags?.length || selectedCocoon?.tags?.length) ? <span className="text-sm text-muted-foreground">No tags</span> : null}
              </div>
            </div>
            <div>
              <div className="mb-2 text-sm text-muted-foreground">Edit Chat Tags</div>
              <div className="rounded-2xl border border-border/70 bg-background/60 p-3">
                <div className="flex flex-wrap gap-2">
                  {(selectedCocoon?.tags || []).map((tag) => (
                    <button
                      key={tag.id}
                      type="button"
                      className="inline-flex items-center rounded-full"
                      onClick={() => void persistTagIds(selectedTagIds.filter((id) => id !== tag.id))}
                      disabled={isUpdatingTags}
                    >
                      <Badge variant="secondary">{tag.name} x</Badge>
                    </button>
                  ))}
                  {!selectedCocoon?.tags?.length ? <span className="text-sm text-muted-foreground">No tags enabled</span> : null}
                </div>
                <div className="mt-3 text-xs text-muted-foreground">
                  Click an existing tag to remove it, or add more tags below.
                </div>
                <div className="mt-3">
                  <Select value={addTagValue} onValueChange={(value) => void handleAddTag(value)} disabled={isUpdatingTags || !availableAddableTags.length}>
                    <SelectTrigger>
                      <SelectValue placeholder="Add tag" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__add">
                        <span className="inline-flex items-center gap-2">
                          <Plus className="size-4" />
                          Add tag
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
              <div className="mb-2 text-sm text-muted-foreground">Current Model</div>
              <Select value={String(session?.currentModelId || selectedCocoon?.selected_model_id || "")} onValueChange={handleChangeModel}>
                <SelectTrigger>
                  <SelectValue placeholder="Select model" />
                </SelectTrigger>
                <SelectContent>
                  {providerModels.map((model) => (
                    <SelectItem key={model.id} value={String(model.id)}>{model.model_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="rounded-2xl border border-border/70 bg-background/70 p-3 text-sm">
              <div className="mb-2 text-muted-foreground">State</div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">Dispatch: {session?.dispatchState || selectedCocoon?.dispatch_status || "idle"}</Badge>
                <Badge variant="outline">Relation: {session?.relationScore ?? "-"}</Badge>
                <Badge variant="outline">
                  Wakeup: {session?.currentWakeupTaskId ? `#${session.currentWakeupTaskId}` : "none"}
                </Badge>
              </div>
              {session?.debounceUntil ? (
                <div className="mt-3 text-xs text-muted-foreground">
                  Debounced until {formatTime(session.debounceUntil)}
                </div>
              ) : null}
              {session?.dispatchReason ? <div className="mt-3 text-xs text-muted-foreground">{session.dispatchReason}</div> : null}
              {session?.lastError ? <div className="mt-3 text-sm text-destructive">{session.lastError}</div> : null}
            </div>
          </CardContent>
        </Card>
        </div>
      </div>
    </PageFrame>
  );
}
