import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  TouchableOpacity,
  Alert,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { saveToken, loadToken } from "../auth/storage";
import { STORAGE_KEYS, DEFAULT_BASE_URL } from "../api/client";

export default function SettingsScreen() {
  const [backendUrl, setBackendUrl] = useState("");
  const [token, setToken] = useState("");

  useEffect(() => {
    (async () => {
      const storedUrl = await AsyncStorage.getItem(STORAGE_KEYS.BASE_URL);
      setBackendUrl(storedUrl ?? DEFAULT_BASE_URL);
      const storedToken = await loadToken();
      setToken(storedToken ?? "");
    })();
  }, []);

  const handleSave = async () => {
    await AsyncStorage.setItem(STORAGE_KEYS.BASE_URL, backendUrl);
    await saveToken(token || null);
    Alert.alert("Settings saved");
  };

  return (
    <View style={styles.container}>
      <Text style={styles.label}>Backend URL</Text>
      <TextInput
        testID="backend-url-input"
        style={styles.input}
        value={backendUrl}
        onChangeText={setBackendUrl}
        placeholder="http://10.0.2.2:7433"
        autoCapitalize="none"
        autoCorrect={false}
      />
      <Text style={styles.label}>Auth Token (JWT)</Text>
      <TextInput
        testID="token-input"
        style={styles.input}
        value={token}
        onChangeText={setToken}
        placeholder="Paste your JWT token"
        autoCapitalize="none"
        autoCorrect={false}
        secureTextEntry
      />
      <TouchableOpacity
        testID="save-button"
        style={styles.button}
        onPress={handleSave}
      >
        <Text style={styles.buttonText}>Save</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20 },
  label: { fontSize: 16, fontWeight: "bold", marginTop: 16, marginBottom: 4 },
  input: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 6,
    padding: 10,
    fontSize: 14,
  },
  button: {
    marginTop: 24,
    backgroundColor: "#007AFF",
    padding: 14,
    borderRadius: 6,
    alignItems: "center",
  },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "bold" },
});
