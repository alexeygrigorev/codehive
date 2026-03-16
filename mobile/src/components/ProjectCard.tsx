import React from "react";
import { TouchableOpacity, View, Text, StyleSheet } from "react-native";
import StatusBadge, { type SessionStatus } from "./StatusBadge";

export interface ProjectCardProps {
  id: string;
  name: string;
  description?: string;
  sessionCount: number;
  status: SessionStatus;
  onPress: () => void;
}

export default function ProjectCard({
  name,
  description,
  sessionCount,
  status,
  onPress,
}: ProjectCardProps) {
  return (
    <TouchableOpacity
      style={styles.card}
      onPress={onPress}
      testID="project-card"
    >
      <View style={styles.header}>
        <Text style={styles.name}>{name}</Text>
        <StatusBadge status={status} />
      </View>
      {description ? (
        <Text style={styles.description} numberOfLines={2}>
          {description}
        </Text>
      ) : null}
      <Text style={styles.sessionCount}>
        {sessionCount} {sessionCount === 1 ? "session" : "sessions"}
      </Text>
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
    marginBottom: 4,
  },
  name: {
    fontSize: 16,
    fontWeight: "600",
    flex: 1,
    marginRight: 8,
  },
  description: {
    fontSize: 14,
    color: "#666",
    marginBottom: 8,
  },
  sessionCount: {
    fontSize: 12,
    color: "#999",
  },
});
