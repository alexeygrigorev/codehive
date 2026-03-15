/**
 * React hook for browser-level Push API notifications.
 * Manages permission state, subscription lifecycle, and backend communication.
 */

import { useState, useEffect, useCallback } from "react";
import { apiClient } from "@/api/client";
import { getRegistration } from "@/sw-register";

function getVapidPublicKey(): string {
  return import.meta.env.VITE_VAPID_PUBLIC_KEY ?? "";
}

/**
 * Convert a base64url string to a Uint8Array for use with PushManager.subscribe.
 */
function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const buffer = new ArrayBuffer(rawData.length);
  const outputArray = new Uint8Array(buffer);
  for (let i = 0; i < rawData.length; i++) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export interface PushNotificationsState {
  permission: NotificationPermission;
  isSubscribed: boolean;
  subscribe: () => Promise<void>;
  unsubscribe: () => Promise<void>;
}

export function usePushNotifications(): PushNotificationsState {
  const [permission, setPermission] = useState<NotificationPermission>(
    typeof Notification !== "undefined" ? Notification.permission : "default",
  );
  const [isSubscribed, setIsSubscribed] = useState(false);

  // Check existing subscription on mount
  useEffect(() => {
    async function check() {
      const reg = getRegistration();
      if (!reg?.pushManager) return;
      try {
        const sub = await reg.pushManager.getSubscription();
        if (sub) {
          setIsSubscribed(true);
        }
      } catch {
        // Push not available
      }
    }
    check();
  }, []);

  const subscribe = useCallback(async () => {
    const vapidKey = getVapidPublicKey();
    if (!vapidKey) {
      console.error("VAPID public key not configured");
      return;
    }

    // Request permission
    const perm = await Notification.requestPermission();
    setPermission(perm);
    if (perm !== "granted") return;

    const reg = getRegistration();
    if (!reg?.pushManager) return;

    try {
      const subscription = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey),
      });

      const json = subscription.toJSON();
      await apiClient.post("/api/push/subscribe", {
        endpoint: json.endpoint,
        keys: {
          p256dh: json.keys?.p256dh ?? "",
          auth: json.keys?.auth ?? "",
        },
      });

      setIsSubscribed(true);
    } catch (error) {
      console.error("Push subscription failed:", error);
    }
  }, []);

  const unsubscribe = useCallback(async () => {
    const reg = getRegistration();
    if (!reg?.pushManager) return;

    try {
      const subscription = await reg.pushManager.getSubscription();
      if (subscription) {
        const endpoint = subscription.endpoint;
        await subscription.unsubscribe();
        await apiClient.post("/api/push/unsubscribe", { endpoint });
      }
      setIsSubscribed(false);
    } catch (error) {
      console.error("Push unsubscription failed:", error);
    }
  }, []);

  return { permission, isSubscribed, subscribe, unsubscribe };
}
