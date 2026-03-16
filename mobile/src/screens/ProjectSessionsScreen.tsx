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
import { listSessions } from "../api/sessions";
import { type SessionStatus } from "../components/StatusBadge";
import SessionCard from "../components/SessionCard";

type Props = NativeStackScreenProps<
  DashboardStackParamList,
  "ProjectSessions"
>;

interface Session {
  id: string;
  name: string;
  mode: string;
  status: SessionStatus;
  updated_at: string;
}

export default function ProjectSessionsScreen({ route, navigation }: Props) {
  const { projectId, projectName } = route.params;
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    navigation.setOptions({ title: projectName });
  }, [navigation, projectName]);

  const fetchSessions = useCallback(async () => {
    try {
      const data = await listSessions(projectId);
      setSessions(data);
    } catch {
      // silently handle for now
    }
  }, [projectId]);

  useEffect(() => {
    (async () => {
      await fetchSessions();
      setLoading(false);
    })();
  }, [fetchSessions]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchSessions();
    setRefreshing(false);
  }, [fetchSessions]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" testID="loading-spinner" />
      </View>
    );
  }

  return (
    <FlatList
      data={sessions}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => (
        <SessionCard
          id={item.id}
          name={item.name}
          mode={item.mode}
          status={item.status}
          updatedAt={item.updated_at}
          onPress={() => {
            navigation.navigate("SessionDetail", { sessionId: item.id });
          }}
        />
      )}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
      contentContainerStyle={
        sessions.length === 0 ? styles.emptyContainer : styles.list
      }
      ListEmptyComponent={
        <Text style={styles.emptyText}>No sessions yet</Text>
      }
      testID="session-list"
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
