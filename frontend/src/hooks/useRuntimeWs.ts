import { useEffect, useRef } from "react";

import type { RuntimeWsEvent } from "@/api/types/chat";

const HEARTBEAT_INTERVAL_MS = 20_000;
const PONG_TIMEOUT_MS = 45_000;
const RECONNECT_DELAYS_MS = [1_000, 2_000, 5_000, 10_000, 15_000];

type RuntimeWsOptions = {
  enabled?: boolean;
  targetKey: string;
  connect: (handlers: {
    onMessage: (event: RuntimeWsEvent) => void;
    onOpen?: () => void;
    onClose?: (event: CloseEvent) => void;
    onError?: (event: Event) => void;
  }) => WebSocket;
  onEvent: (event: RuntimeWsEvent) => void;
  onRecover?: () => Promise<void> | void;
  onError?: (message: string) => void;
};

export function useRuntimeWs({
  enabled = true,
  targetKey,
  connect,
  onEvent,
  onRecover,
  onError,
}: RuntimeWsOptions) {
  const socketRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<number | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const closedByEffectRef = useRef(false);
  const hasConnectedRef = useRef(false);
  const lastPongAtRef = useRef(Date.now());
  const connectRef = useRef(connect);
  const onEventRef = useRef(onEvent);
  const onRecoverRef = useRef(onRecover);
  const onErrorRef = useRef(onError);

  connectRef.current = connect;
  onEventRef.current = onEvent;
  onRecoverRef.current = onRecover;
  onErrorRef.current = onError;

  useEffect(() => {
    if (!enabled || !targetKey.trim()) {
      return;
    }

    closedByEffectRef.current = false;

    function emitError(message: string) {
      onErrorRef.current?.(message);
    }

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
        openSocket();
      }, delay);
    }

    function openSocket() {
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

      const socket = connectRef.current({
        onOpen: () => {
          if (socketRef.current !== socket) {
            return;
          }

          reconnectAttemptRef.current = 0;
          lastPongAtRef.current = Date.now();
          const shouldRecover = hasConnectedRef.current;
          hasConnectedRef.current = true;

          heartbeatRef.current = window.setInterval(() => {
            const liveSocket = socketRef.current;
            if (!liveSocket || liveSocket.readyState !== WebSocket.OPEN) {
              return;
            }
            if (Date.now() - lastPongAtRef.current > PONG_TIMEOUT_MS) {
              liveSocket.close(4000, "pong timeout");
              return;
            }
            liveSocket.send(JSON.stringify({ type: "ping" }));
          }, HEARTBEAT_INTERVAL_MS);

          if (shouldRecover) {
            void onRecoverRef.current?.();
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
          onEventRef.current(event);
        },
        onError: () => {
          if (socketRef.current !== socket) {
            return;
          }
          emitError("Realtime connection error");
        },
        onClose: () => {
          if (socketRef.current === socket) {
            socketRef.current = null;
          }
          clearHeartbeat();
          if (!closedByEffectRef.current) {
            emitError("Realtime connection lost, reconnecting...");
            scheduleReconnect();
          }
        },
      });

      socketRef.current = socket;
    }

    openSocket();

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
  }, [enabled, targetKey]);
}
