import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { DashboardStackParamList } from "../navigation/types";
import { finalizeFlow, type ProjectBrief } from "../api/projectFlow";

type Props = NativeStackScreenProps<DashboardStackParamList, "BriefReview">;

export default function BriefReviewScreen({ route, navigation }: Props) {
  const { flowId, brief: initialBrief } = route.params;
  const [name, setName] = useState(initialBrief.name);
  const [description, setDescription] = useState(initialBrief.description);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const brief: ProjectBrief = {
    ...initialBrief,
    name,
    description,
  };

  const handleCreate = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await finalizeFlow(flowId);
      navigation.navigate("ProjectSessions", {
        projectId: result.project_id,
        projectName: name,
      });
    } catch {
      setError("Failed to create project. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.heading}>Project Brief</Text>

      <Text style={styles.label}>Project Name</Text>
      <TextInput
        style={styles.nameInput}
        value={name}
        onChangeText={setName}
        testID="brief-name-input"
      />

      <Text style={styles.label}>Description</Text>
      <TextInput
        style={styles.descriptionInput}
        value={description}
        onChangeText={setDescription}
        multiline
        testID="brief-description-input"
      />

      <Text style={styles.sectionTitle}>Tech Stack</Text>
      {brief.tech_stack.map((tech, idx) => (
        <Text key={idx} style={styles.listItem} testID={`tech-stack-${idx}`}>
          {tech}
        </Text>
      ))}

      <Text style={styles.sectionTitle}>Architecture</Text>
      <Text style={styles.bodyText} testID="architecture-text">
        {brief.architecture}
      </Text>

      {brief.open_decisions.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>Open Decisions</Text>
          {brief.open_decisions.map((decision, idx) => (
            <Text
              key={idx}
              style={styles.listItem}
              testID={`open-decision-${idx}`}
            >
              {decision}
            </Text>
          ))}
        </>
      )}

      {brief.suggested_sessions.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>Suggested Sessions</Text>
          {brief.suggested_sessions.map((session, idx) => (
            <View
              key={idx}
              style={styles.sessionCard}
              testID={`suggested-session-${idx}`}
            >
              <Text style={styles.sessionName}>{session.name}</Text>
              <Text style={styles.sessionMission}>{session.mission}</Text>
              <Text style={styles.sessionMode}>Mode: {session.mode}</Text>
            </View>
          ))}
        </>
      )}

      <TouchableOpacity
        style={styles.createButton}
        onPress={handleCreate}
        disabled={loading}
        testID="create-project-button"
      >
        <Text style={styles.createButtonText}>Create Project</Text>
      </TouchableOpacity>

      {loading && (
        <ActivityIndicator
          size="large"
          style={styles.loader}
          testID="loading-indicator"
        />
      )}

      {error && (
        <Text style={styles.errorText} testID="error-message">
          {error}
        </Text>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 16,
  },
  heading: {
    fontSize: 22,
    fontWeight: "bold",
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: "500",
    marginBottom: 4,
    color: "#333",
  },
  nameInput: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    marginBottom: 16,
  },
  descriptionInput: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
    minHeight: 80,
    textAlignVertical: "top",
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "600",
    marginTop: 16,
    marginBottom: 8,
  },
  bodyText: {
    fontSize: 14,
    color: "#444",
    lineHeight: 20,
  },
  listItem: {
    fontSize: 14,
    color: "#444",
    paddingLeft: 8,
    marginBottom: 4,
  },
  sessionCard: {
    backgroundColor: "#f5f5f5",
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
  },
  sessionName: {
    fontSize: 15,
    fontWeight: "600",
  },
  sessionMission: {
    fontSize: 13,
    color: "#555",
    marginTop: 2,
  },
  sessionMode: {
    fontSize: 12,
    color: "#888",
    marginTop: 4,
  },
  createButton: {
    backgroundColor: "#4CAF50",
    borderRadius: 8,
    padding: 16,
    alignItems: "center",
    marginTop: 24,
  },
  createButtonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "bold",
  },
  loader: {
    marginTop: 16,
  },
  errorText: {
    color: "#d32f2f",
    fontSize: 14,
    marginTop: 12,
    textAlign: "center",
  },
});
