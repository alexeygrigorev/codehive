import AsyncStorage from "@react-native-async-storage/async-storage";
import apiClient, { DEFAULT_BASE_URL, STORAGE_KEYS } from "../src/api/client";
import { saveToken } from "../src/auth/storage";

beforeEach(async () => {
  await AsyncStorage.clear();
});

describe("api/client", () => {
  it("uses default base URL when none is stored", () => {
    expect(apiClient.defaults.baseURL).toBe(DEFAULT_BASE_URL);
  });

  it("default base URL targets Android emulator localhost", () => {
    expect(DEFAULT_BASE_URL).toBe("http://10.0.2.2:7433");
  });

  it("request interceptor attaches Authorization header when token exists", async () => {
    await saveToken("test-jwt-token");

    // Simulate running the interceptor by creating a mock config
    const interceptors = (apiClient.interceptors.request as any).handlers;
    const interceptorFn = interceptors[0].fulfilled;

    const config = {
      headers: { set: jest.fn(), get: jest.fn() } as any,
      baseURL: DEFAULT_BASE_URL,
    };

    const result = await interceptorFn(config);
    expect(result.headers.Authorization).toBe("Bearer test-jwt-token");
  });

  it("request interceptor does not attach Authorization header when no token", async () => {
    const interceptors = (apiClient.interceptors.request as any).handlers;
    const interceptorFn = interceptors[0].fulfilled;

    const config = {
      headers: {} as any,
      baseURL: DEFAULT_BASE_URL,
    };

    const result = await interceptorFn(config);
    expect(result.headers.Authorization).toBeUndefined();
  });

  it("request interceptor uses stored base URL", async () => {
    await AsyncStorage.setItem(STORAGE_KEYS.BASE_URL, "http://10.0.0.5:8000");

    const interceptors = (apiClient.interceptors.request as any).handlers;
    const interceptorFn = interceptors[0].fulfilled;

    const config = {
      headers: {} as any,
      baseURL: DEFAULT_BASE_URL,
    };

    const result = await interceptorFn(config);
    expect(result.baseURL).toBe("http://10.0.0.5:8000");
  });
});
