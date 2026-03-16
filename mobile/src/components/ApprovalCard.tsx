import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";

export interface Approval {
  id: string;
  session_id: string;
  tool_name: string;
  tool_input?: Record<string, unknown>;
  description: string;
  status: string;
  created_at: string;
}

export interface ApprovalCardProps {
  approval: Approval;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

function formatTimestamp(dateString: string): string {
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return "unknown";
  return date.toLocaleString();
}

export default function ApprovalCard({
  approval,
  onApprove,
  onReject,
}: ApprovalCardProps) {
  return (
    <View style={styles.card} testID="approval-card">
      <Text style={styles.description} testID="approval-description">
        {approval.description}
      </Text>
      <Text style={styles.toolName} testID="approval-tool-name">
        Tool: {approval.tool_name}
      </Text>
      <Text style={styles.meta} testID="approval-session">
        Session: {approval.session_id}
      </Text>
      <Text style={styles.meta} testID="approval-timestamp">
        {formatTimestamp(approval.created_at)}
      </Text>
      <View style={styles.buttonRow}>
        <TouchableOpacity
          style={[styles.button, styles.approveButton]}
          onPress={() => onApprove(approval.id)}
          testID="approve-button"
        >
          <Text style={styles.approveText}>Approve</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.button, styles.rejectButton]}
          onPress={() => onReject(approval.id)}
          testID="reject-button"
        >
          <Text style={styles.rejectText}>Reject</Text>
        </TouchableOpacity>
      </View>
    </View>
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
  description: {
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 8,
  },
  toolName: {
    fontSize: 13,
    color: "#1565C0",
    marginBottom: 4,
  },
  meta: {
    fontSize: 12,
    color: "#999",
    marginBottom: 2,
  },
  buttonRow: {
    flexDirection: "row",
    marginTop: 12,
    gap: 10,
  },
  button: {
    flex: 1,
    borderRadius: 6,
    paddingVertical: 10,
    alignItems: "center",
  },
  approveButton: {
    backgroundColor: "#4CAF50",
  },
  rejectButton: {
    backgroundColor: "#F44336",
  },
  approveText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "600",
  },
  rejectText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "600",
  },
});
