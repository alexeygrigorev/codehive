import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import SettingsScreen from "../src/screens/SettingsScreen";
import { STORAGE_KEYS } from "../src/api/client";

beforeEach(async () => {
  await AsyncStorage.clear();
});

describe("SettingsScreen", () => {
  it("renders backend URL and token inputs", () => {
    render(<SettingsScreen />);

    expect(screen.getByTestId("backend-url-input")).toBeTruthy();
    expect(screen.getByTestId("token-input")).toBeTruthy();
    expect(screen.getByTestId("save-button")).toBeTruthy();
  });

  it("renders labels for the fields", () => {
    render(<SettingsScreen />);

    expect(screen.getByText("Backend URL")).toBeTruthy();
    expect(screen.getByText("Auth Token (JWT)")).toBeTruthy();
  });

  it("persists values to AsyncStorage when save is pressed", async () => {
    render(<SettingsScreen />);

    const urlInput = screen.getByTestId("backend-url-input");
    const tokenInput = screen.getByTestId("token-input");
    const saveButton = screen.getByTestId("save-button");

    fireEvent.changeText(urlInput, "http://myserver.com:9000");
    fireEvent.changeText(tokenInput, "my-jwt-token");
    fireEvent.press(saveButton);

    await waitFor(async () => {
      const storedUrl = await AsyncStorage.getItem(STORAGE_KEYS.BASE_URL);
      expect(storedUrl).toBe("http://myserver.com:9000");
    });

    await waitFor(async () => {
      const storedToken = await AsyncStorage.getItem("codehive_auth_token");
      expect(storedToken).toBe("my-jwt-token");
    });
  });
});
