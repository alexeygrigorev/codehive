import React from "react";
import { View, Text, StyleSheet } from "react-native";

export interface ToolCallResultProps {
  metadata: {
    tool_name?: string;
    result?: string;
  };
}

const MAX_RESULT_LENGTH = 200;

export default function ToolCallResult({ metadata }: ToolCallResultProps) {
  const toolName = metadata.tool_name ?? "unknown tool";
  const result = metadata.result ?? "";
  const truncated =
    result.length > MAX_RESULT_LENGTH
      ? result.slice(0, MAX_RESULT_LENGTH) + "..."
      : result;

  return (
    <View style={styles.container} testID="tool-call-result">
      <Text style={styles.toolName}>{toolName}</Text>
      {truncated.length > 0 && (
        <Text style={styles.result} testID="tool-result-text">
          {truncated}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#F5F5F5",
    borderRadius: 6,
    padding: 10,
    borderLeftWidth: 3,
    borderLeftColor: "#9E9E9E",
  },
  toolName: {
    fontFamily: "monospace",
    fontSize: 12,
    fontWeight: "700",
    color: "#333",
    marginBottom: 4,
  },
  result: {
    fontFamily: "monospace",
    fontSize: 11,
    color: "#666",
  },
});
