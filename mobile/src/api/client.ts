import axios from "axios";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { loadToken } from "../auth/storage";

export const DEFAULT_BASE_URL = "http://10.0.2.2:7433";

export const STORAGE_KEYS = {
  BASE_URL: "codehive_base_url",
  AUTH_DISABLED: "codehive_auth_disabled",
} as const;

const apiClient = axios.create({
  baseURL: DEFAULT_BASE_URL,
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

/** Check /api/auth/config and cache the result. */
export async function checkAuthConfig(): Promise<boolean> {
  try {
    const storedUrl = await AsyncStorage.getItem(STORAGE_KEYS.BASE_URL);
    const base = storedUrl || DEFAULT_BASE_URL;
    const response = await fetch(`${base}/api/auth/config`);
    if (response.ok) {
      const data = (await response.json()) as { auth_enabled: boolean };
      await AsyncStorage.setItem(
        STORAGE_KEYS.AUTH_DISABLED,
        data.auth_enabled ? "false" : "true",
      );
      return data.auth_enabled;
    }
  } catch {
    // If unreachable, assume auth enabled (safe default)
  }
  return true;
}

/** Returns true when the backend has auth disabled. */
export async function isAuthDisabled(): Promise<boolean> {
  const val = await AsyncStorage.getItem(STORAGE_KEYS.AUTH_DISABLED);
  return val === "true";
}

// Request interceptor: set base URL and auth token from storage before each request
apiClient.interceptors.request.use(async (config) => {
  const storedUrl = await AsyncStorage.getItem(STORAGE_KEYS.BASE_URL);
  if (storedUrl) {
    config.baseURL = storedUrl;
  }

  const authOff = await isAuthDisabled();
  if (!authOff) {
    const token = await loadToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }

  return config;
});

export default apiClient;
