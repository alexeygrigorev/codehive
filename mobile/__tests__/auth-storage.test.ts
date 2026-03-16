import AsyncStorage from "@react-native-async-storage/async-storage";
import { saveToken, loadToken, clearToken } from "../src/auth/storage";

// jest-expo provides AsyncStorage mock automatically via the preset
// but we need to clear it between tests
beforeEach(async () => {
  await AsyncStorage.clear();
});

describe("auth/storage", () => {
  it("saveToken then loadToken returns the saved token", async () => {
    await saveToken("abc123");
    const result = await loadToken();
    expect(result).toBe("abc123");
  });

  it("clearToken then loadToken returns null", async () => {
    await saveToken("abc123");
    await clearToken();
    const result = await loadToken();
    expect(result).toBeNull();
  });

  it("loadToken returns null when no token is stored", async () => {
    const result = await loadToken();
    expect(result).toBeNull();
  });

  it("saveToken(null) clears the token", async () => {
    await saveToken("abc123");
    await saveToken(null);
    const result = await loadToken();
    expect(result).toBeNull();
  });
});
