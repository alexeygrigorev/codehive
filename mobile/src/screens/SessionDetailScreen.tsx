import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  FlatList,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { SessionsStackParamList } from "../navigation/types";
import { getSession, getMessages, sendMessage } from "../api/sessions";
import { useEvents } from "../context/EventContext";
import { type SessionStatus } from "../components/StatusBadge";
import SessionHeader from "../components/SessionHeader";
import MessageBubble, { type Message } from "../components/MessageBubble";
import VoiceButton from "../components/VoiceButton";

type Props = NativeStackScreenProps<SessionsStackParamList, "SessionDetail">;

interface SessionData {
  id: string;
  name: string;
  mode: string;
  status: SessionStatus;
}

export default function SessionDetailScreen({ route, navigation }: Props) {
  const { sessionId } = route.params;
  const [session, setSession] = useState<SessionData | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [inputText, setInputText] = useState("");
  const [sending, setSending] = useState(false);
  const flatListRef = useRef<FlatList>(null);
  const events = useEvents();

  const handleVoiceTranscript = useCallback((text: string) => {
    setInputText((prev) => (prev ? `${prev} ${text}` : text));
  }, []);

  const fetchData = useCallback(async () => {
    try {
      const [sessionData, messagesData] = await Promise.all([
        getSession(sessionId),
        getMessages(sessionId),
      ]);
      setSession(sessionData);
      setMessages(messagesData);
      setError(null);
    } catch (_e) {
      setError("Failed to load session");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // WebSocket connection
  useEffect(() => {
    events.connect(sessionId);
    return () => {
      events.disconnect();
    };
  }, [sessionId, events]);

  // WebSocket event listener
  useEffect(() => {
    const handler = (event: unknown) => {
      const evt = event as { type?: string; data?: Record<string, unknown> };
      if (!evt.type || !evt.data) return;

      if (evt.type === "message.created") {
        const msg = evt.data as unknown as Message;
        setMessages((prev) => [...prev, msg]);
      } else if (evt.type === "session.status_changed") {
        const newStatus = evt.data.status as SessionStatus;
        setSession((prev) =>
          prev ? { ...prev, status: newStatus } : prev
        );
      }
    };

    events.addListener(handler);
    return () => {
      events.removeListener(handler);
    };
  }, [events]);

  const handleSend = useCallback(async () => {
    const text = inputText.trim();
    if (!text) return;

    const optimisticMsg: Message = {
      id: `temp-${Date.now()}`,
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, optimisticMsg]);
    setInputText("");
    setSending(true);

    try {
      await sendMessage(sessionId, text);
    } catch (_e) {
      // keep the optimistic message; could add error indicator later
    } finally {
      setSending(false);
    }
  }, [inputText, sessionId]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" testID="loading-spinner" />
      </View>
    );
  }

  if (error || !session) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText} testID="error-text">
          {error ?? "Session not found"}
        </Text>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <SessionHeader
        name={session.name}
        mode={session.mode}
        status={session.status}
        onBack={() => navigation.goBack()}
      />
      <FlatList
        ref={flatListRef}
        data={messages}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <MessageBubble message={item} />}
        inverted={false}
        contentContainerStyle={styles.messageList}
        testID="message-list"
      />
      <View style={styles.inputContainer}>
        <TextInput
          style={styles.textInput}
          value={inputText}
          onChangeText={setInputText}
          placeholder="Type a message..."
          testID="message-input"
          returnKeyType="send"
          onSubmitEditing={handleSend}
        />
        <VoiceButton
          onTranscript={handleVoiceTranscript}
          disabled={sending}
        />
        <TouchableOpacity
          style={styles.sendButton}
          onPress={handleSend}
          testID="send-button"
        >
          <Text style={styles.sendText}>Send</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
    backgroundColor: "#FAFAFA",
  },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  errorText: {
    fontSize: 16,
    color: "#F44336",
  },
  messageList: {
    paddingVertical: 8,
  },
  inputContainer: {
    flexDirection: "row",
    alignItems: "center",
    padding: 8,
    backgroundColor: "#fff",
    borderTopWidth: 1,
    borderTopColor: "#E0E0E0",
  },
  textInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: "#DDD",
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 8,
    fontSize: 15,
    marginRight: 8,
  },
  sendButton: {
    backgroundColor: "#2196F3",
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  sendText: {
    color: "#fff",
    fontWeight: "600",
    fontSize: 14,
  },
});
