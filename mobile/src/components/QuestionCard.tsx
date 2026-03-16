import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
} from "react-native";

export interface Question {
  id: string;
  session_id: string;
  question: string;
  context?: string;
  answered: boolean;
  answer?: string;
  created_at: string;
}

export interface QuestionCardProps {
  question: Question;
  onAnswer: (id: string, answer: string) => void;
}

function formatTimestamp(dateString: string): string {
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return "unknown";
  return date.toLocaleString();
}

export default function QuestionCard({ question, onAnswer }: QuestionCardProps) {
  const [answerText, setAnswerText] = useState("");

  const handleSubmit = () => {
    if (answerText.trim()) {
      onAnswer(question.id, answerText.trim());
      setAnswerText("");
    }
  };

  return (
    <View style={styles.card} testID="question-card">
      <Text style={styles.questionText} testID="question-text">
        {question.question}
      </Text>
      <Text style={styles.meta} testID="question-session">
        Session: {question.session_id}
      </Text>
      <Text style={styles.meta} testID="question-timestamp">
        {formatTimestamp(question.created_at)}
      </Text>
      {question.answered ? (
        <View style={styles.answerContainer}>
          <Text style={styles.answerLabel}>Answer:</Text>
          <Text style={styles.answerText} testID="question-answer">
            {question.answer}
          </Text>
        </View>
      ) : (
        <View style={styles.inputContainer}>
          <TextInput
            style={styles.input}
            placeholder="Type your answer..."
            value={answerText}
            onChangeText={setAnswerText}
            testID="answer-input"
          />
          <TouchableOpacity
            style={[
              styles.submitButton,
              !answerText.trim() && styles.submitButtonDisabled,
            ]}
            onPress={handleSubmit}
            disabled={!answerText.trim()}
            testID="submit-answer"
          >
            <Text
              style={[
                styles.submitText,
                !answerText.trim() && styles.submitTextDisabled,
              ]}
            >
              Submit
            </Text>
          </TouchableOpacity>
        </View>
      )}
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
  questionText: {
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 8,
  },
  meta: {
    fontSize: 12,
    color: "#999",
    marginBottom: 2,
  },
  answerContainer: {
    marginTop: 12,
    backgroundColor: "#F5F5F5",
    borderRadius: 6,
    padding: 12,
  },
  answerLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: "#666",
    marginBottom: 4,
  },
  answerText: {
    fontSize: 14,
    color: "#333",
  },
  inputContainer: {
    marginTop: 12,
  },
  input: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 6,
    padding: 10,
    fontSize: 14,
    marginBottom: 8,
  },
  submitButton: {
    backgroundColor: "#1565C0",
    borderRadius: 6,
    paddingVertical: 10,
    alignItems: "center",
  },
  submitButtonDisabled: {
    backgroundColor: "#ccc",
  },
  submitText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "600",
  },
  submitTextDisabled: {
    color: "#999",
  },
});
