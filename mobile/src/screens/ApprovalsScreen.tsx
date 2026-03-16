import React, { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  StyleSheet,
} from "react-native";
import {
  listPendingApprovals,
  approve,
  reject,
} from "../api/approvals";
import ApprovalCard, { type Approval } from "../components/ApprovalCard";

export default function ApprovalsScreen() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchApprovals = useCallback(async () => {
    try {
      const data: Approval[] = await listPendingApprovals();
      setApprovals(data);
    } catch {
      // silently handle for now
    }
  }, []);

  useEffect(() => {
    (async () => {
      await fetchApprovals();
      setLoading(false);
    })();
  }, [fetchApprovals]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchApprovals();
    setRefreshing(false);
  }, [fetchApprovals]);

  const handleApprove = useCallback(async (id: string) => {
    try {
      await approve(id);
      setApprovals((prev) => prev.filter((a) => a.id !== id));
    } catch {
      // silently handle for now
    }
  }, []);

  const handleReject = useCallback(async (id: string) => {
    try {
      await reject(id);
      setApprovals((prev) => prev.filter((a) => a.id !== id));
    } catch {
      // silently handle for now
    }
  }, []);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" testID="loading-spinner" />
      </View>
    );
  }

  return (
    <FlatList
      data={approvals}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => (
        <ApprovalCard
          approval={item}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      )}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
      contentContainerStyle={
        approvals.length === 0 ? styles.emptyContainer : styles.list
      }
      ListEmptyComponent={
        <Text style={styles.emptyText}>No pending approvals</Text>
      }
      testID="approvals-list"
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
