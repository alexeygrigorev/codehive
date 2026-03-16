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
import { listIssues } from "../api/issues";
import { type IssueStatus } from "../components/IssueStatusBadge";
import IssueCard from "../components/IssueCard";

type Props = NativeStackScreenProps<
  DashboardStackParamList,
  "ProjectIssues"
>;

interface Issue {
  id: string;
  title: string;
  status: IssueStatus;
  created_at: string;
}

export default function ProjectIssuesScreen({ route, navigation }: Props) {
  const { projectId, projectName } = route.params;
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    navigation.setOptions({ title: projectName });
  }, [navigation, projectName]);

  const fetchIssues = useCallback(async () => {
    try {
      const data = await listIssues(projectId);
      setIssues(data);
    } catch {
      // silently handle for now
    }
  }, [projectId]);

  useEffect(() => {
    (async () => {
      await fetchIssues();
      setLoading(false);
    })();
  }, [fetchIssues]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchIssues();
    setRefreshing(false);
  }, [fetchIssues]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" testID="loading-spinner" />
      </View>
    );
  }

  return (
    <FlatList
      data={issues}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => (
        <IssueCard
          id={item.id}
          title={item.title}
          status={item.status}
          createdAt={item.created_at}
          onPress={() => {
            // Issue detail screen is out of scope for this issue
          }}
        />
      )}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
      contentContainerStyle={
        issues.length === 0 ? styles.emptyContainer : styles.list
      }
      ListEmptyComponent={
        <Text style={styles.emptyText}>No issues yet</Text>
      }
      testID="issue-list"
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
