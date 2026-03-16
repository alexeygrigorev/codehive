import * as Notifications from "expo-notifications";
import type { NavigationContainerRef } from "@react-navigation/native";
import type { RootTabParamList } from "../navigation/types";

/**
 * Set up notification listeners for incoming notifications and tap responses.
 * Returns a cleanup function to remove listeners.
 */
export function setupNotificationHandler(
  navigationRef: NavigationContainerRef<RootTabParamList>,
): () => void {
  const receivedSubscription =
    Notifications.addNotificationReceivedListener((_notification) => {
      // Notification received in foreground - no navigation needed
    });

  const responseSubscription =
    Notifications.addNotificationResponseReceivedListener((response) => {
      const data = response.notification.request.content.data as Record<
        string,
        string
      >;
      const eventType = data?.event_type;
      const sessionId = data?.session_id;

      if (!eventType) {
        return;
      }

      switch (eventType) {
        case "approval.required":
          navigationRef.navigate("Approvals" as any);
          break;
        case "session.completed":
        case "session.failed":
          if (sessionId) {
            navigationRef.navigate("Sessions" as any, {
              screen: "SessionDetail",
              params: { sessionId },
            });
          }
          break;
        case "question.created":
          navigationRef.navigate("Questions" as any);
          break;
        default:
          break;
      }
    });

  return () => {
    receivedSubscription.remove();
    responseSubscription.remove();
  };
}
