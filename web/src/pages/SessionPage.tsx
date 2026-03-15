import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { WebSocketProvider } from "@/context/WebSocketContext";
import { apiClient } from "@/api/client";
import type { SessionRead } from "@/api/sessions";
import ChatPanel from "@/components/ChatPanel";

export default function SessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [session, setSession] = useState<SessionRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;

    async function load() {
      try {
        const response = await apiClient.get(`/api/sessions/${sessionId}`);
        if (!response.ok) {
          throw new Error(`Failed to load session: ${response.status}`);
        }
        const data = (await response.json()) as SessionRead;
        if (!cancelled) {
          setSession(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load session",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  if (loading) {
    return (
      <div>
        <h1 className="text-2xl font-bold">Session</h1>
        <p className="text-gray-500 mt-4">Loading session...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <h1 className="text-2xl font-bold">Session</h1>
        <p className="text-red-600 mt-4">{error}</p>
      </div>
    );
  }

  if (!session || !sessionId) {
    return (
      <div>
        <h1 className="text-2xl font-bold">Session</h1>
        <p className="text-red-600 mt-4">Session not found</p>
      </div>
    );
  }

  const statusColors: Record<string, string> = {
    idle: "bg-gray-100 text-gray-700",
    planning: "bg-yellow-100 text-yellow-800",
    executing: "bg-blue-100 text-blue-800",
    waiting_input: "bg-purple-100 text-purple-800",
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
  };

  const statusClass =
    statusColors[session.status] ?? "bg-gray-100 text-gray-700";

  return (
    <WebSocketProvider sessionId={sessionId}>
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
          <h1 className="text-xl font-bold text-gray-900">{session.name}</h1>
          <span
            className={`session-status inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${statusClass}`}
          >
            {session.status}
          </span>
        </div>
        <div className="flex-1 min-h-0">
          <ChatPanel sessionId={sessionId} />
        </div>
      </div>
    </WebSocketProvider>
  );
}
