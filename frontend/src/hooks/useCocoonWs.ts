import { useEffect, useEffectEvent, useRef } from "react";

import { connectCocoonWorkspaceSocket } from "@/api/cocoons";
import type { RuntimeWsEvent } from "@/api/types";

const HEARTBEAT_INTERVAL_MS = 20_000;
const PONG_TIMEOUT_MS = 45_000;
const RECONNECT_DELAYS_MS = [1_000, 2_000, 5_000, 10_000, 15_000];

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
  const socketRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<number | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const closedByEffectRef = useRef(false);
  const hasConnectedRef = useRef(false);
  const lastPongAtRef = useRef(Date.now());

  const handleEvent = useEffectEvent(onEvent);
  const handleRecover = useEffectEvent(async () => {
    await onRecover?.();
  });
  const handleError = useEffectEvent((message: string) => {
    onError?.(message);
  });

  useEffect(() => {
    if (!enabled || !Number.isFinite(cocoonId) || cocoonId <= 0) {
      return;
    }

    closedByEffectRef.current = false;

    function clearHeartbeat() {
      if (heartbeatRef.current !== null) {
        window.clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
    }

    function clearReconnectTimer() {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    }

    function scheduleReconnect() {
      if (closedByEffectRef.current || reconnectTimerRef.current !== null) {
        return;
      }
      const attempt = reconnectAttemptRef.current;
      const delay = RECONNECT_DELAYS_MS[Math.min(attempt, RECONNECT_DELAYS_MS.length - 1)];
      reconnectAttemptRef.current = attempt + 1;
      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null;
        connect();
      }, delay);
    }

    function connect() {
      clearHeartbeat();
      clearReconnectTimer();

      const previousSocket = socketRef.current;
      if (previousSocket) {
        previousSocket.onopen = null;
        previousSocket.onmessage = null;
        previousSocket.onerror = null;
        previousSocket.onclose = null;
        previousSocket.close();
      }

      const socket = connectCocoonWorkspaceSocket(cocoonId, {
        onOpen: () => {
          if (socketRef.current !== socket) {
            return;
          }
          reconnectAttemptRef.current = 0;
          lastPongAtRef.current = Date.now();
          const shouldRecover = hasConnectedRef.current;
          hasConnectedRef.current = true;

          heartbeatRef.current = window.setInterval(() => {
            const socket = socketRef.current;
            if (!socket || socket.readyState !== WebSocket.OPEN) {
              return;
            }
            if (Date.now() - lastPongAtRef.current > PONG_TIMEOUT_MS) {
              socket.close(4000, "pong timeout");
              return;
            }
            socket.send(JSON.stringify({ type: "ping" }));
          }, HEARTBEAT_INTERVAL_MS);

          if (shouldRecover) {
            void handleRecover();
          }
        },
        onMessage: (event) => {
          if (socketRef.current !== socket) {
            return;
          }
          if (event.type === "pong") {
            lastPongAtRef.current = Date.now();
            return;
          }
          handleEvent(event);
        },
        onError: () => {
          if (socketRef.current !== socket) {
            return;
          }
          handleError("Realtime connection error");
        },
        onClose: () => {
          if (socketRef.current === socket) {
            socketRef.current = null;
          }
          clearHeartbeat();
          if (!closedByEffectRef.current) {
            handleError("Realtime connection lost, reconnecting...");
            scheduleReconnect();
          }
        },
      });
      socketRef.current = socket;
    }

    connect();

    return () => {
      closedByEffectRef.current = true;
      clearHeartbeat();
      clearReconnectTimer();
      if (socketRef.current) {
        socketRef.current.onopen = null;
        socketRef.current.onmessage = null;
        socketRef.current.onerror = null;
        socketRef.current.onclose = null;
        socketRef.current.close();
      }
      socketRef.current = null;
    };
  }, [cocoonId, enabled]);
}
