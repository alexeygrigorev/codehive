import React, { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  StyleSheet,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { DashboardStackParamList } from "../navigation/types";
import { listProjects } from "../api/projects";
import { type SessionStatus } from "../components/StatusBadge";
import ProjectCard from "../components/ProjectCard";

type Props = NativeStackScreenProps<DashboardStackParamList, "DashboardHome">;

interface Session {
  status: SessionStatus;
}

interface Project {
  id: string;
  name: string;
  description?: string;
  sessions?: Session[];
}

function deriveProjectStatus(sessions: Session[]): SessionStatus {
  if (sessions.length === 0) return "idle";

  const redStatuses: SessionStatus[] = ["failed", "blocked"];
  const yellowStatuses: SessionStatus[] = [
    "planning",
    "executing",
    "waiting_input",
    "waiting_approval",
  ];

  for (const s of sessions) {
    if (redStatuses.includes(s.status)) return s.status;
  }
  for (const s of sessions) {
    if (yellowStatuses.includes(s.status)) return s.status;
  }
  return "idle";
}

export default function DashboardScreen({ navigation }: Props) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchProjects = useCallback(async () => {
    try {
      const data = await listProjects();
      setProjects(data);
    } catch {
      // silently handle for now
    }
  }, []);

  useEffect(() => {
    (async () => {
      await fetchProjects();
      setLoading(false);
    })();
  }, [fetchProjects]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchProjects();
    setRefreshing(false);
  }, [fetchProjects]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" testID="loading-spinner" />
      </View>
    );
  }

  return (
    <FlatList
      data={projects}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => {
        const sessions = item.sessions ?? [];
        return (
          <ProjectCard
            id={item.id}
            name={item.name}
            description={item.description}
            sessionCount={sessions.length}
            status={deriveProjectStatus(sessions)}
            onPress={() =>
              navigation.navigate("ProjectSessions", {
                projectId: item.id,
                projectName: item.name,
              })
            }
          />
        );
      }}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
      contentContainerStyle={
        projects.length === 0 ? styles.emptyContainer : styles.list
      }
      ListEmptyComponent={
        <Text style={styles.emptyText}>No projects yet</Text>
      }
      testID="project-list"
    />
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  list: {
    paddingVertical: 8,
  },
  emptyContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  emptyText: {
    fontSize: 16,
    color: "#999",
  },
});
