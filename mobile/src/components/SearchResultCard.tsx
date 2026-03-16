import React from "react";
import { TouchableOpacity, View, Text, StyleSheet } from "react-native";
import type { SearchResult } from "../api/search";

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

const TYPE_COLORS: Record<string, string> = {
  session: "#1565C0",
  message: "#6A1B9A",
  issue: "#E65100",
  event: "#2E7D32",
};

interface SearchResultCardProps {
  result: SearchResult;
  onPress: () => void;
}

export default function SearchResultCard({
  result,
  onPress,
}: SearchResultCardProps) {
  const badgeColor = TYPE_COLORS[result.type] || "#757575";
  return (
    <TouchableOpacity
      style={styles.card}
      onPress={onPress}
      testID="search-result-card"
    >
      <View style={styles.header}>
        <View style={[styles.typeBadge, { backgroundColor: badgeColor }]}>
          <Text style={styles.typeBadgeText}>{result.type}</Text>
        </View>
        <Text style={styles.timestamp}>
          {formatRelativeTime(result.created_at)}
        </Text>
      </View>
      <Text style={styles.snippet} numberOfLines={2}>
        {result.snippet}
      </Text>
      {result.project_name ? (
        <Text style={styles.meta} testID="project-name">
          {result.project_name}
          {result.session_name ? ` / ${result.session_name}` : ""}
        </Text>
      ) : result.session_name ? (
        <Text style={styles.meta} testID="session-name">
          {result.session_name}
        </Text>
      ) : null}
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
  typeBadge: {
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  typeBadgeText: {
    fontSize: 12,
    color: "#fff",
    fontWeight: "600",
  },
  timestamp: {
    fontSize: 12,
    color: "#999",
  },
  snippet: {
    fontSize: 14,
    color: "#333",
    marginBottom: 4,
  },
  meta: {
    fontSize: 12,
    color: "#666",
  },
});
