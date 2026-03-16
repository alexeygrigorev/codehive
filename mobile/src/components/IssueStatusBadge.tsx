import React from "react";
import { View, Text, StyleSheet } from "react-native";

export type IssueStatus = "open" | "in_progress" | "closed";

function getIssueStatusColor(status: IssueStatus): string {
  switch (status) {
    case "open":
      return "#2196F3";
    case "in_progress":
      return "#FFC107";
    case "closed":
      return "#4CAF50";
    default:
      return "#9E9E9E";
  }
}

interface IssueStatusBadgeProps {
  status: IssueStatus;
}

export default function IssueStatusBadge({ status }: IssueStatusBadgeProps) {
  const color = getIssueStatusColor(status);
  return (
    <View style={styles.container} testID="issue-status-badge">
      <View
        style={[styles.dot, { backgroundColor: color }]}
        testID="issue-status-dot"
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
