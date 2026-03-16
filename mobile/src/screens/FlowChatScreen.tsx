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
import { respondToFlow, type FlowQuestion } from "../api/projectFlow";

type Props = NativeStackScreenProps<DashboardStackParamList, "FlowChat">;

export default function FlowChatScreen({ route, navigation }: Props) {
  const { flowId, questions: initialQuestions } = route.params;
  const [questions, setQuestions] = useState<FlowQuestion[]>(initialQuestions);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnswerChange = (questionId: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      const flowAnswers = questions.map((q) => ({
        question_id: q.id,
        answer: answers[q.id] || "",
      }));
      const result = await respondToFlow(flowId, flowAnswers);
      if (result.brief) {
        navigation.navigate("BriefReview", {
          flowId,
          brief: result.brief,
        });
      } else if (result.next_questions) {
        setQuestions(result.next_questions);
        setAnswers({});
      }
    } catch {
      setError("Failed to submit answers. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Group questions by category
  const grouped = questions.reduce<Record<string, FlowQuestion[]>>(
    (acc, q) => {
      const cat = q.category || "General";
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(q);
      return acc;
    },
    {},
  );

  return (
    <ScrollView contentContainerStyle={styles.container}>
      {Object.entries(grouped).map(([category, categoryQuestions]) => (
        <View key={category} style={styles.categorySection}>
          <Text style={styles.categoryLabel} testID={`category-${category}`}>
            {category}
          </Text>
          {categoryQuestions.map((q) => (
            <View key={q.id} style={styles.questionBlock}>
              <Text style={styles.questionText} testID={`question-${q.id}`}>
                {q.text}
              </Text>
              <TextInput
                style={styles.answerInput}
                value={answers[q.id] || ""}
                onChangeText={(val) => handleAnswerChange(q.id, val)}
                placeholder="Type your answer..."
                multiline
                testID={`answer-${q.id}`}
              />
            </View>
          ))}
        </View>
      ))}

      <TouchableOpacity
        style={styles.submitButton}
        onPress={handleSubmit}
        disabled={loading}
        testID="submit-button"
      >
        <Text style={styles.submitButtonText}>Submit</Text>
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
  categorySection: {
    marginBottom: 16,
  },
  categoryLabel: {
    fontSize: 16,
    fontWeight: "600",
    color: "#333",
    marginBottom: 8,
  },
  questionBlock: {
    marginBottom: 16,
  },
  questionText: {
    fontSize: 14,
    fontWeight: "500",
    marginBottom: 6,
  },
  answerInput: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
    minHeight: 60,
    textAlignVertical: "top",
  },
  submitButton: {
    backgroundColor: "#2196F3",
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
    marginTop: 8,
  },
  submitButtonText: {
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
