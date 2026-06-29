'use client';

import { useEffect, useRef } from 'react';
import { getWsBaseUrl } from '@/utils/api';

export type AlertEvent = {
  type: string;
  data: Record<string, unknown>;
};

export function useAlertWebSocket(
  codigoIbge: string | undefined,
  onAlert: (event: AlertEvent) => void,
) {
  const cbRef = useRef(onAlert);
  cbRef.current = onAlert;

  useEffect(() => {
    if (!codigoIbge) return;

    let ws: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const connect = () => {
      if (closed) return;
      ws = new WebSocket(`${getWsBaseUrl()}/ws/alerts/${codigoIbge}`);
      ws.onmessage = (ev) => {
        try {
          const parsed = JSON.parse(ev.data) as AlertEvent;
          cbRef.current(parsed);
        } catch {
          /* ignore */
        }
      };
      ws.onclose = () => {
        if (!closed) retryTimer = setTimeout(connect, 8000);
      };
    };

    connect();

    return () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      ws?.close();
    };
  }, [codigoIbge]);
}
