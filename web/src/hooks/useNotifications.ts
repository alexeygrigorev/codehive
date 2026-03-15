import { useMemo } from "react";
import { useWebSocket } from "@/context/WebSocketContext.tsx";

interface NotificationCounts {
  pendingQuestions: number;
  pendingApprovals: number;
}

export function useNotifications(): NotificationCounts {
  const { events } = useWebSocket();

  return useMemo(() => {
    let pendingQuestions = 0;
    let pendingApprovals = 0;

    for (const event of events) {
      if (event.type === "approval.required") {
        pendingApprovals++;
      }
      if (
        event.type === "session.waiting" &&
        event.data?.reason === "pending_question"
      ) {
        pendingQuestions++;
      }
    }

    return { pendingQuestions, pendingApprovals };
  }, [events]);
}
