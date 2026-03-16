import { registerForPushNotifications } from "../src/notifications/setup";

// Mock expo-notifications
jest.mock("expo-notifications", () => ({
  getPermissionsAsync: jest.fn(),
  requestPermissionsAsync: jest.fn(),
  getExpoPushTokenAsync: jest.fn(),
}));

// Mock expo-device
jest.mock("expo-device", () => ({
  isDevice: true,
}));

// Mock react-native Platform
jest.mock("react-native", () => ({
  Platform: { OS: "android" },
}));

// Mock api client
const mockPost = jest.fn().mockResolvedValue({ data: { status: "registered" } });
jest.mock("../src/api/client", () => ({
  __esModule: true,
  default: {
    post: (...args: unknown[]) => mockPost(...args),
  },
}));

import * as Notifications from "expo-notifications";
import * as Device from "expo-device";

describe("registerForPushNotifications", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (Device as any).isDevice = true;
  });

  it("requests permission, obtains token, and posts to backend", async () => {
    (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({
      status: "granted",
    });
    (Notifications.getExpoPushTokenAsync as jest.Mock).mockResolvedValue({
      data: "ExponentPushToken[abc123]",
    });

    const token = await registerForPushNotifications();

    expect(token).toBe("ExponentPushToken[abc123]");
    expect(Notifications.getPermissionsAsync).toHaveBeenCalled();
    expect(Notifications.getExpoPushTokenAsync).toHaveBeenCalled();
    expect(mockPost).toHaveBeenCalledWith("/api/push/register-device", {
      token: "ExponentPushToken[abc123]",
      platform: "android",
    });
  });

  it("does not register token when permission denied", async () => {
    (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({
      status: "denied",
    });
    (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({
      status: "denied",
    });

    const token = await registerForPushNotifications();

    expect(token).toBeNull();
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("returns null on non-physical device", async () => {
    (Device as any).isDevice = false;

    const token = await registerForPushNotifications();

    expect(token).toBeNull();
    expect(mockPost).not.toHaveBeenCalled();
  });
});
