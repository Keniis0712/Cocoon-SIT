import { connectCocoonWorkspaceSocket } from "@/api/cocoons";
import { useRuntimeWs } from "@/hooks/useRuntimeWs";
import type { RuntimeWsEvent } from "@/api/types/chat";

type CocoonWsOptions = {
  cocoonId: number;
  enabled?: boolean;
  onEvent: (event: RuntimeWsEvent) => void;
  onRecover?: () => Promise<void> | void;
  onError?: (message: string) => void;
};

export function useCocoonWs({
  cocoonId,
  enabled = true,
  onEvent,
  onRecover,
  onError,
}: CocoonWsOptions) {
  useRuntimeWs({
    enabled: enabled && Number.isFinite(cocoonId) && cocoonId > 0,
    targetKey: String(cocoonId),
    connect: (handlers) => connectCocoonWorkspaceSocket(cocoonId, handlers),
    onEvent,
    onRecover,
    onError,
  });
}
