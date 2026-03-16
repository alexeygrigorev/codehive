import axios from "axios";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { loadToken } from "../auth/storage";

export const DEFAULT_BASE_URL = "http://10.0.2.2:7433";

export const STORAGE_KEYS = {
  BASE_URL: "codehive_base_url",
} as const;

const apiClient = axios.create({
  baseURL: DEFAULT_BASE_URL,
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

// Request interceptor: set base URL and auth token from storage before each request
apiClient.interceptors.request.use(async (config) => {
  const storedUrl = await AsyncStorage.getItem(STORAGE_KEYS.BASE_URL);
  if (storedUrl) {
    config.baseURL = storedUrl;
  }

  const token = await loadToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

export default apiClient;
