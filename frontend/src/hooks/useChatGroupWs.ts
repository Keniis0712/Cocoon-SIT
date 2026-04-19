import { connectChatGroupWorkspaceSocket } from "@/api/chatGroups";
import { useRuntimeWs } from "@/hooks/useRuntimeWs";
import type { RuntimeWsEvent } from "@/api/types/chat";

type ChatGroupWsOptions = {
  roomId: string;
  enabled?: boolean;
  onEvent: (event: RuntimeWsEvent) => void;
  onRecover?: () => Promise<void> | void;
  onError?: (message: string) => void;
};

export function useChatGroupWs({
  roomId,
  enabled = true,
  onEvent,
  onRecover,
  onError,
}: ChatGroupWsOptions) {
  useRuntimeWs({
    enabled: enabled && Boolean(roomId.trim()),
    targetKey: roomId,
    connect: (handlers) => connectChatGroupWorkspaceSocket(roomId, handlers),
    onEvent,
    onRecover,
    onError,
  });
}
