import { useMemo } from "react";
import { useWebSocket } from "@/context/WebSocketContext.tsx";
import type { SessionEvent } from "@/api/websocket.ts";

export function useSessionEvents(typeFilter?: string[]): SessionEvent[] {
  const { events } = useWebSocket();

  return useMemo(() => {
    if (!typeFilter || typeFilter.length === 0) {
      return events;
    }
    const filterSet = new Set(typeFilter);
    return events.filter((e) => filterSet.has(e.type));
  }, [events, typeFilter]);
}
