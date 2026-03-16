import React from "react";
import { View, Text, StyleSheet } from "react-native";
import ToolCallResult from "./ToolCallResult";

export interface Message {
  id: string;
  role: string;
  content: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const { role, content, metadata } = message;

  if (role === "system") {
    return (
      <View style={styles.systemContainer} testID="message-bubble-system">
        <Text style={styles.systemText}>{content}</Text>
      </View>
    );
  }

  if (role === "tool") {
    return (
      <View style={styles.toolContainer} testID="message-bubble-tool">
        <ToolCallResult
          metadata={{
            tool_name: (metadata?.tool_name as string) ?? undefined,
            result: content || ((metadata?.result as string) ?? undefined),
          }}
        />
      </View>
    );
  }

  const isUser = role === "user";

  return (
    <View
      style={[
        styles.bubbleContainer,
        isUser ? styles.userContainer : styles.assistantContainer,
      ]}
      testID={isUser ? "message-bubble-user" : "message-bubble-assistant"}
    >
      <View
        style={[styles.bubble, isUser ? styles.userBubble : styles.assistantBubble]}
      >
        <Text
          style={[styles.text, isUser ? styles.userText : styles.assistantText]}
        >
          {content}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bubbleContainer: {
    paddingHorizontal: 12,
    paddingVertical: 4,
  },
  userContainer: {
    alignItems: "flex-end",
  },
  assistantContainer: {
    alignItems: "flex-start",
  },
  bubble: {
    maxWidth: "80%",
    borderRadius: 16,
    padding: 12,
  },
  userBubble: {
    backgroundColor: "#2196F3",
  },
  assistantBubble: {
    backgroundColor: "#E0E0E0",
  },
  text: {
    fontSize: 15,
  },
  userText: {
    color: "#FFFFFF",
  },
  assistantText: {
    color: "#212121",
  },
  systemContainer: {
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  systemText: {
    fontStyle: "italic",
    color: "#999",
    fontSize: 13,
  },
  toolContainer: {
    alignItems: "flex-start",
    paddingHorizontal: 12,
    paddingVertical: 4,
  },
});
