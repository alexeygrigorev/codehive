/// <reference lib="webworker" />

declare const self: ServiceWorkerGlobalScope;

const CACHE_NAME = "codehive-app-shell-v1";

const APP_SHELL_URLS = ["/", "/index.html", "/manifest.json"];

// Install: cache app shell assets
self.addEventListener("install", (event: ExtendableEvent) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL_URLS)),
  );
  // Activate immediately without waiting for existing clients to close
  self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener("activate", (event: ExtendableEvent) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key)),
      ),
    ),
  );
  // Claim all open clients immediately
  self.clients.claim();
});

// Fetch: serve from cache with network fallback
self.addEventListener("fetch", (event: FetchEvent) => {
  // Only handle GET requests
  if (event.request.method !== "GET") return;

  // Skip API and WebSocket requests
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/ws/")) return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        // Don't cache non-OK or opaque responses
        if (!response || response.status !== 200 || response.type === "opaque") {
          return response;
        }
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      });
    }),
  );
});

// Push: show notification from push event payload
self.addEventListener("push", (event: PushEvent) => {
  if (!event.data) return;

  let payload: { title?: string; body?: string; icon?: string; url?: string };
  try {
    payload = event.data.json();
  } catch {
    payload = { title: "Codehive", body: event.data.text() };
  }

  const title = payload.title ?? "Codehive";
  const options: NotificationOptions = {
    body: payload.body ?? "",
    icon: payload.icon ?? "/icons/icon-192x192.png",
    data: { url: payload.url ?? "/" },
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// Notification click: focus or open the app window
self.addEventListener("notificationclick", (event: NotificationEvent) => {
  event.notification.close();

  const url = (event.notification.data?.url as string) ?? "/";

  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((clientList) => {
      // Focus an existing window if possible
      for (const client of clientList) {
        if ("focus" in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      // Otherwise open a new window
      return self.clients.openWindow(url);
    }),
  );
});

export {};
