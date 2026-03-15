import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { usePushNotifications } from "@/hooks/usePushNotifications";

// Mock the sw-register module
vi.mock("@/sw-register", () => {
  const mockSubscription = {
    endpoint: "https://push.example.com/sub1",
    toJSON: () => ({
      endpoint: "https://push.example.com/sub1",
      keys: { p256dh: "test-p256dh", auth: "test-auth" },
    }),
    unsubscribe: vi.fn().mockResolvedValue(true),
  };

  const mockPushManager = {
    getSubscription: vi.fn().mockResolvedValue(null),
    subscribe: vi.fn().mockResolvedValue(mockSubscription),
  };

  const mockRegistration = {
    pushManager: mockPushManager,
  };

  return {
    getRegistration: vi.fn(() => mockRegistration),
    _mockPushManager: mockPushManager,
    _mockSubscription: mockSubscription,
  };
});

// Mock the api client
vi.mock("@/api/client", () => ({
  apiClient: {
    baseURL: "http://localhost:8000",
    post: vi.fn().mockResolvedValue({ ok: true }),
    get: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

// We need to import these after the mocks are set up
import { apiClient } from "@/api/client";

// Access mock internals
const swRegisterModule = await import("@/sw-register");
const mockPushManager = (swRegisterModule as any)._mockPushManager;
const mockSubscription = (swRegisterModule as any)._mockSubscription;

describe("usePushNotifications", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: no existing subscription
    mockPushManager.getSubscription.mockResolvedValue(null);

    // Mock Notification API
    vi.stubGlobal("Notification", {
      permission: "default",
      requestPermission: vi.fn().mockResolvedValue("granted"),
    });

    // Set VAPID key via import.meta.env
    import.meta.env.VITE_VAPID_PUBLIC_KEY = "dGVzdC12YXBpZC1rZXk";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns default permission and isSubscribed=false on mount", () => {
    const { result } = renderHook(() => usePushNotifications());

    expect(result.current.permission).toBe("default");
    expect(result.current.isSubscribed).toBe(false);
  });

  it("detects existing subscription on mount and sets isSubscribed=true", async () => {
    mockPushManager.getSubscription.mockResolvedValue(mockSubscription);

    const { result } = renderHook(() => usePushNotifications());

    await waitFor(() => {
      expect(result.current.isSubscribed).toBe(true);
    });
  });

  it("subscribe() requests permission and POSTs subscription to backend", async () => {
    // Simulate Notification.requestPermission returning "granted"
    vi.stubGlobal("Notification", {
      permission: "default",
      requestPermission: vi.fn().mockResolvedValue("granted"),
    });

    const { result } = renderHook(() => usePushNotifications());

    await act(async () => {
      await result.current.subscribe();
    });

    // Verify PushManager.subscribe was called
    expect(mockPushManager.subscribe).toHaveBeenCalledWith({
      userVisibleOnly: true,
      applicationServerKey: expect.any(Uint8Array),
    });

    // Verify backend was called
    expect(apiClient.post).toHaveBeenCalledWith("/api/push/subscribe", {
      endpoint: "https://push.example.com/sub1",
      keys: { p256dh: "test-p256dh", auth: "test-auth" },
    });

    expect(result.current.isSubscribed).toBe(true);
  });

  it("unsubscribe() calls subscription.unsubscribe and POSTs to backend", async () => {
    // Start with an existing subscription
    mockPushManager.getSubscription.mockResolvedValue(mockSubscription);

    const { result } = renderHook(() => usePushNotifications());

    await waitFor(() => {
      expect(result.current.isSubscribed).toBe(true);
    });

    await act(async () => {
      await result.current.unsubscribe();
    });

    expect(mockSubscription.unsubscribe).toHaveBeenCalled();
    expect(apiClient.post).toHaveBeenCalledWith("/api/push/unsubscribe", {
      endpoint: "https://push.example.com/sub1",
    });
    expect(result.current.isSubscribed).toBe(false);
  });
});
