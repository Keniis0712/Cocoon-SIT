import type { RuntimeWsEvent } from "@/api/types/chat";

type RuntimeWsMessageMapper<TMessage> = (message: TMessage) => any;

type RuntimeWsOptions = {
  mapModelId?: (modelId: string | number | null | undefined) => number | null;
};

export function mapRuntimeWsEvent<TMessage>(
  event: any,
  mapMessage: RuntimeWsMessageMapper<TMessage>,
  options: RuntimeWsOptions = {},
): RuntimeWsEvent {
  if (event.type === "reply_started") {
    return event.user_message ? { ...event, user_message: mapMessage(event.user_message) } : event;
  }
  if (event.type === "reply_chunk") {
    return {
      ...event,
      delta: typeof event.delta === "string" ? event.delta : typeof event.text === "string" ? event.text : "",
      flush: Boolean(event.flush),
    } as RuntimeWsEvent;
  }
  if (event.type === "reply_done") {
    return event.assistant_message ? { ...event, assistant_message: mapMessage(event.assistant_message) } : event;
  }
  if (event.type === "state_patch") {
    return {
      ...event,
      current_wakeup_task_id: event.current_wakeup_task_id ?? null,
      current_model_id: options.mapModelId ? options.mapModelId(event.current_model_id) : event.current_model_id ?? null,
    } as RuntimeWsEvent;
  }
  return event as RuntimeWsEvent;
}

