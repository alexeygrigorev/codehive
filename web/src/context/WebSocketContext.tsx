import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
} from "react";
import type { ReactNode } from "react";
import {
  WebSocketClient,
} from "@/api/websocket.ts";
import type {
  SessionEvent,
  ConnectionState,
  EventCallback,
} from "@/api/websocket.ts";

interface WebSocketContextValue {
  connectionState: ConnectionState;
  events: SessionEvent[];
  onEvent: (callback: EventCallback) => void;
  removeListener: (callback: EventCallback) => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

interface WebSocketProviderProps {
  sessionId: string | null;
  children: ReactNode;
}

export function WebSocketProvider({
  sessionId,
  children,
}: WebSocketProviderProps) {
  const clientRef = useRef<WebSocketClient | null>(null);
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("disconnected");
  const [events, setEvents] = useState<SessionEvent[]>([]);

  useEffect(() => {
    if (!clientRef.current) {
      clientRef.current = new WebSocketClient();
    }
    const client = clientRef.current;

    const handleEvent: EventCallback = (event) => {
      setEvents((prev) => [...prev, event]);
    };

    const handleState = (state: ConnectionState) => {
      setConnectionState(state);
    };

    client.onEvent(handleEvent);
    client.onStateChange(handleState);

    if (sessionId) {
      setEvents([]);
      client.connect(sessionId);
    } else {
      client.disconnect();
    }

    return () => {
      client.removeListener(handleEvent);
      client.removeStateListener(handleState);
      client.disconnect();
    };
  }, [sessionId]);

  const onEvent = useCallback((callback: EventCallback) => {
    clientRef.current?.onEvent(callback);
  }, []);

  const removeListener = useCallback((callback: EventCallback) => {
    clientRef.current?.removeListener(callback);
  }, []);

  const value: WebSocketContextValue = {
    connectionState,
    events,
    onEvent,
    removeListener,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocket(): WebSocketContextValue {
  const context = useContext(WebSocketContext);
  if (context === null) {
    throw new Error("useWebSocket must be used within a WebSocketProvider");
  }
  return context;
}
