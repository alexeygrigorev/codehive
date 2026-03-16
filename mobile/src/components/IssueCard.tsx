import React from "react";
import { TouchableOpacity, View, Text, StyleSheet } from "react-native";
import IssueStatusBadge, { type IssueStatus } from "./IssueStatusBadge";

export interface IssueCardProps {
  id: string;
  title: string;
  status: IssueStatus;
  createdAt: string;
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

export default function IssueCard({
  title,
  status,
  createdAt,
  onPress,
}: IssueCardProps) {
  return (
    <TouchableOpacity
      style={styles.card}
      onPress={onPress}
      testID="issue-card"
    >
      <View style={styles.header}>
        <Text style={styles.title}>{title}</Text>
        <IssueStatusBadge status={status} />
      </View>
      <Text style={styles.timestamp}>{formatRelativeTime(createdAt)}</Text>
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
  title: {
    fontSize: 16,
    fontWeight: "600",
    flex: 1,
    marginRight: 8,
  },
  timestamp: {
    fontSize: 12,
    color: "#999",
  },
});
