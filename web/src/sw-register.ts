/**
 * Service worker registration logic.
 * Registers the service worker on app load and provides access to the active registration.
 */

let swRegistration: ServiceWorkerRegistration | null = null;

/**
 * Register the service worker. Should be called once on app load.
 * Returns the ServiceWorkerRegistration on success, or null if unavailable.
 */
export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (!("serviceWorker" in navigator)) {
    return null;
  }

  try {
    const registration = await navigator.serviceWorker.register("/service-worker.js", {
      scope: "/",
    });
    swRegistration = registration;

    // Handle updates
    registration.addEventListener("updatefound", () => {
      const newWorker = registration.installing;
      if (newWorker) {
        newWorker.addEventListener("statechange", () => {
          if (
            newWorker.state === "activated" &&
            navigator.serviceWorker.controller
          ) {
            // New service worker activated; app can notify user of update
            console.log("Service worker updated and activated.");
          }
        });
      }
    });

    return registration;
  } catch (error) {
    console.error("Service worker registration failed:", error);
    return null;
  }
}

/**
 * Get the current active service worker registration.
 * Returns null if not yet registered.
 */
export function getRegistration(): ServiceWorkerRegistration | null {
  return swRegistration;
}
