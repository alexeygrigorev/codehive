import React from "react";
import { View, Text, StyleSheet } from "react-native";

export type SessionStatus =
  | "idle"
  | "completed"
  | "planning"
  | "executing"
  | "waiting_input"
  | "waiting_approval"
  | "failed"
  | "blocked";

const GREEN_STATUSES: SessionStatus[] = ["idle", "completed"];
const YELLOW_STATUSES: SessionStatus[] = [
  "planning",
  "executing",
  "waiting_input",
  "waiting_approval",
];
const RED_STATUSES: SessionStatus[] = ["failed", "blocked"];

function getStatusColor(status: SessionStatus): string {
  if (GREEN_STATUSES.includes(status)) return "#4CAF50";
  if (YELLOW_STATUSES.includes(status)) return "#FFC107";
  if (RED_STATUSES.includes(status)) return "#F44336";
  return "#9E9E9E";
}

interface StatusBadgeProps {
  status: SessionStatus;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const color = getStatusColor(status);
  return (
    <View style={styles.container} testID="status-badge">
      <View
        style={[styles.dot, { backgroundColor: color }]}
        testID="status-dot"
      />
      <Text style={styles.label}>{status}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 6,
  },
  label: {
    fontSize: 12,
    color: "#666",
  },
});
