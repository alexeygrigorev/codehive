import React from "react";
import { TouchableOpacity, View, Text, StyleSheet } from "react-native";
import StatusBadge, { type SessionStatus } from "./StatusBadge";

export interface SessionCardProps {
  id: string;
  name: string;
  mode: string;
  status: SessionStatus;
  updatedAt: string;
  onPress: () => void;
}

function formatRelativeTime(dateString: string): string {
  const now = Date.now();
  const then = new Date(dateString).getTime();
  const diffMs = now - then;

  if (isNaN(then)) return "unknown";

  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function SessionCard({
  name,
  mode,
  status,
  updatedAt,
  onPress,
}: SessionCardProps) {
  return (
    <TouchableOpacity
      style={styles.card}
      onPress={onPress}
      testID="session-card"
    >
      <View style={styles.header}>
        <Text style={styles.name}>{name}</Text>
        <StatusBadge status={status} />
      </View>
      <View style={styles.footer}>
        <View style={styles.modeChip}>
          <Text style={styles.modeText}>{mode}</Text>
        </View>
        <Text style={styles.timestamp}>{formatRelativeTime(updatedAt)}</Text>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#fff",
    borderRadius: 8,
    padding: 16,
    marginHorizontal: 16,
    marginVertical: 6,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  name: {
    fontSize: 16,
    fontWeight: "600",
    flex: 1,
    marginRight: 8,
  },
  footer: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
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
  timestamp: {
    fontSize: 12,
    color: "#999",
  },
});
