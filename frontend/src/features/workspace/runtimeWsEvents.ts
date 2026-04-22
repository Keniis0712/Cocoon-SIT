import type { RuntimeWsEvent } from "@/api/types/chat";

type RuntimeWsHandlerDeps = {
  sessionKey: string | number;
  upsertMessage: (sessionKey: string | number, message: any) => void;
  setStreamingAssistant: (sessionKey: string | number, value: string) => void;
  appendStreamingAssistant: (sessionKey: string | number, value: string) => void;
  applyStatePatch: (
    sessionKey: string | number,
    patch: {
      relationScore?: number | null;
      personaJson?: Record<string, unknown>;
      activeTags?: string[];
      currentModelId?: number | null;
      currentWakeupTaskId?: string | null;
      dispatchState?: string;
      dispatchReason?: string | null;
      debounceUntil?: string | null;
    },
  ) => void;
  setError: (sessionKey: string | number, error: string | null) => void;
  reloadWorkspace: () => void;
  reloadWakeups?: () => void;
  scrollToBottom?: () => void;
  onRoundFailed?: (detail: string) => void;
};

export function createRuntimeWsEventHandler({
  sessionKey,
  upsertMessage,
  setStreamingAssistant,
  appendStreamingAssistant,
  applyStatePatch,
  setError,
  reloadWorkspace,
  reloadWakeups,
  scrollToBottom,
  onRoundFailed,
}: RuntimeWsHandlerDeps) {
  return function handleRuntimeWsEvent(event: RuntimeWsEvent) {
    if (event.type === "reply_started") {
      if ("user_message" in event && event.user_message) {
        upsertMessage(sessionKey, event.user_message);
      }
      setStreamingAssistant(sessionKey, "");
      applyStatePatch(sessionKey, { dispatchState: "running", dispatchReason: null });
      return;
    }
    if (event.type === "reply_chunk") {
      appendStreamingAssistant(sessionKey, event.delta);
      return;
    }
    if (event.type === "reply_done") {
      if ("assistant_message" in event && event.assistant_message) {
        upsertMessage(sessionKey, event.assistant_message);
      } else {
        reloadWorkspace();
      }
      reloadWakeups?.();
      setStreamingAssistant(sessionKey, "");
      applyStatePatch(sessionKey, { dispatchState: "idle", dispatchReason: null });
      if (scrollToBottom) {
        queueMicrotask(scrollToBottom);
      }
      return;
    }
    if (event.type === "state_patch") {
      applyStatePatch(sessionKey, {
        relationScore: event.relation_score,
        personaJson: event.persona_json,
        activeTags: event.active_tags,
        currentModelId: event.current_model_id,
        currentWakeupTaskId: event.current_wakeup_task_id ?? null,
        dispatchState: "idle",
        dispatchReason: null,
      });
      reloadWakeups?.();
      return;
    }
    if (event.type === "dispatch_queued") {
      applyStatePatch(sessionKey, {
        dispatchState: event.status || "queued",
        dispatchReason: event.reason ?? null,
        debounceUntil: event.debounce_until ?? null,
      });
      return;
    }
    if (event.type === "round_failed") {
      setStreamingAssistant(sessionKey, "");
      setError(sessionKey, event.error_detail);
      applyStatePatch(sessionKey, { dispatchState: "error" });
      reloadWakeups?.();
      onRoundFailed?.(event.error_detail);
    }
  };
}
