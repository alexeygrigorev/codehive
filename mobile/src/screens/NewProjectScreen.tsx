import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  StyleSheet,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { DashboardStackParamList } from "../navigation/types";
import { startFlow } from "../api/projectFlow";

type Props = NativeStackScreenProps<DashboardStackParamList, "NewProject">;

interface FlowTypeCard {
  type: string;
  title: string;
  description: string;
  requiresInput: boolean;
}

const FLOW_TYPES: FlowTypeCard[] = [
  {
    type: "brainstorm",
    title: "Brainstorm",
    description: "Free-form ideation to explore your project idea",
    requiresInput: false,
  },
  {
    type: "interview",
    title: "Guided Interview",
    description: "Structured questions to define your requirements",
    requiresInput: false,
  },
  {
    type: "from_notes",
    title: "From Notes",
    description: "Start from existing notes or a project description",
    requiresInput: true,
  },
  {
    type: "from_repo",
    title: "From Repository",
    description: "Import and analyze an existing repository",
    requiresInput: true,
  },
];

export default function NewProjectScreen({ navigation }: Props) {
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [initialInput, setInitialInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedCard = FLOW_TYPES.find((f) => f.type === selectedType);

  const handleStartFlow = async (flowType: string, input?: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await startFlow({
        flow_type: flowType,
        initial_input: input,
      });
      navigation.navigate("FlowChat", {
        flowId: result.flow_id,
        questions: result.first_questions,
      });
    } catch {
      setError("Failed to start project flow. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleCardPress = (card: FlowTypeCard) => {
    if (card.requiresInput) {
      setSelectedType(card.type);
      setInitialInput("");
      setError(null);
    } else {
      handleStartFlow(card.type);
    }
  };

  const handleContinue = () => {
    if (selectedType && initialInput.trim()) {
      handleStartFlow(selectedType, initialInput.trim());
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.heading}>Start a New Project</Text>

      {FLOW_TYPES.map((card) => (
        <TouchableOpacity
          key={card.type}
          style={[
            styles.card,
            selectedType === card.type && styles.cardSelected,
          ]}
          onPress={() => handleCardPress(card)}
          testID={`flow-card-${card.type}`}
          disabled={loading}
        >
          <Text style={styles.cardTitle}>{card.title}</Text>
          <Text style={styles.cardDescription}>{card.description}</Text>
        </TouchableOpacity>
      ))}

      {selectedCard?.requiresInput && (
        <View style={styles.inputSection} testID="initial-input-section">
          <Text style={styles.inputLabel}>
            {selectedType === "from_notes"
              ? "Paste your notes:"
              : "Repository URL or path:"}
          </Text>
          <TextInput
            style={styles.textInput}
            value={initialInput}
            onChangeText={setInitialInput}
            placeholder={
              selectedType === "from_notes"
                ? "Enter your project notes..."
                : "Enter repository URL..."
            }
            multiline
            testID="initial-input"
          />
          <TouchableOpacity
            style={[
              styles.continueButton,
              !initialInput.trim() && styles.continueButtonDisabled,
            ]}
            onPress={handleContinue}
            disabled={!initialInput.trim() || loading}
            testID="continue-button"
          >
            <Text style={styles.continueButtonText}>Continue</Text>
          </TouchableOpacity>
        </View>
      )}

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
  card: {
    backgroundColor: "#f5f5f5",
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 2,
    borderColor: "transparent",
  },
  cardSelected: {
    borderColor: "#2196F3",
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: "600",
    marginBottom: 4,
  },
  cardDescription: {
    fontSize: 14,
    color: "#666",
  },
  inputSection: {
    marginTop: 8,
    marginBottom: 12,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: "500",
    marginBottom: 8,
  },
  textInput: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
    minHeight: 80,
    textAlignVertical: "top",
  },
  continueButton: {
    backgroundColor: "#2196F3",
    borderRadius: 8,
    padding: 14,
    marginTop: 12,
    alignItems: "center",
  },
  continueButtonDisabled: {
    opacity: 0.5,
  },
  continueButtonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
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
