import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
} from "react";
import { SessionWebSocket, type EventHandler } from "../api/ws";

interface EventContextValue {
  lastEvent: unknown | null;
  connect: (sessionId: string) => void;
  disconnect: () => void;
  addListener: (handler: EventHandler) => void;
  removeListener: (handler: EventHandler) => void;
}

const EventContext = createContext<EventContextValue>({
  lastEvent: null,
  connect: () => {},
  disconnect: () => {},
  addListener: () => {},
  removeListener: () => {},
});

export function EventProvider({ children }: { children: React.ReactNode }) {
  const [lastEvent, setLastEvent] = useState<unknown | null>(null);
  const wsRef = useRef<SessionWebSocket | null>(null);
  const externalListeners = useRef<Set<EventHandler>>(new Set());

  const handleEvent: EventHandler = useCallback((event: unknown) => {
    setLastEvent(event);
    externalListeners.current.forEach((listener) => listener(event));
  }, []);

  const connect = useCallback(
    (sessionId: string) => {
      if (wsRef.current) {
        wsRef.current.disconnect();
      }
      const ws = new SessionWebSocket(sessionId);
      ws.addListener(handleEvent);
      ws.connect();
      wsRef.current = ws;
    },
    [handleEvent]
  );

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.disconnect();
      wsRef.current = null;
    }
  }, []);

  const addListener = useCallback((handler: EventHandler) => {
    externalListeners.current.add(handler);
  }, []);

  const removeListener = useCallback((handler: EventHandler) => {
    externalListeners.current.delete(handler);
  }, []);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.disconnect();
      }
    };
  }, []);

  return (
    <EventContext.Provider
      value={{ lastEvent, connect, disconnect, addListener, removeListener }}
    >
      {children}
    </EventContext.Provider>
  );
}

export function useEvents() {
  return useContext(EventContext);
}

export default EventContext;
