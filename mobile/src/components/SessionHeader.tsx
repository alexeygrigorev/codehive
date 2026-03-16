import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import StatusBadge, { type SessionStatus } from "./StatusBadge";

interface SessionHeaderProps {
  name: string;
  mode: string;
  status: SessionStatus;
  onBack: () => void;
}

export default function SessionHeader({
  name,
  mode,
  status,
  onBack,
}: SessionHeaderProps) {
  return (
    <View style={styles.container} testID="session-header">
      <TouchableOpacity onPress={onBack} testID="back-button">
        <Text style={styles.backText}>Back</Text>
      </TouchableOpacity>
      <View style={styles.titleRow}>
        <Text style={styles.name} numberOfLines={1}>
          {name}
        </Text>
      </View>
      <View style={styles.metaRow}>
        <View style={styles.modeChip}>
          <Text style={styles.modeText}>{mode}</Text>
        </View>
        <StatusBadge status={status} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#fff",
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#E0E0E0",
  },
  backText: {
    fontSize: 16,
    color: "#2196F3",
    marginBottom: 8,
  },
  titleRow: {
    marginBottom: 6,
  },
  name: {
    fontSize: 18,
    fontWeight: "700",
    color: "#212121",
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  modeChip: {
    backgroundColor: "#E3F2FD",
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  modeText: {
    fontSize: 12,
    color: "#1565C0",
  },
});
