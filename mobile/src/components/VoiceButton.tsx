import React, { useCallback, useEffect } from "react";
import { TouchableOpacity, Text, StyleSheet, View } from "react-native";
import { useVoiceRecognition } from "../hooks/useVoiceRecognition";

interface VoiceButtonProps {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}

export default function VoiceButton({
  onTranscript,
  disabled,
}: VoiceButtonProps) {
  const {
    isListening,
    transcript,
    error,
    isAvailable,
    startListening,
    stopListening,
  } = useVoiceRecognition();

  useEffect(() => {
    if (transcript) {
      onTranscript(transcript);
    }
  }, [transcript, onTranscript]);

  const handlePress = useCallback(async () => {
    if (disabled) return;
    if (isListening) {
      await stopListening();
    } else {
      await startListening();
    }
  }, [disabled, isListening, startListening, stopListening]);

  if (!isAvailable) {
    return null;
  }

  return (
    <View>
      <TouchableOpacity
        testID="voice-button"
        style={[
          styles.button,
          isListening && styles.buttonListening,
          disabled && styles.buttonDisabled,
        ]}
        onPress={handlePress}
        disabled={disabled}
        accessibilityLabel={isListening ? "Stop voice input" : "Start voice input"}
        accessibilityRole="button"
      >
        <Text
          style={[styles.icon, isListening && styles.iconListening]}
          testID="voice-button-icon"
        >
          {isListening ? "Stop" : "Mic"}
        </Text>
      </TouchableOpacity>
      {isListening && (
        <Text style={styles.listeningLabel} testID="listening-label">
          Listening...
        </Text>
      )}
      {error && (
        <Text style={styles.errorLabel} testID="voice-error">
          {error}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  button: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#E0E0E0",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 8,
  },
  buttonListening: {
    backgroundColor: "#F44336",
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  icon: {
    fontSize: 14,
    fontWeight: "600",
    color: "#333",
  },
  iconListening: {
    color: "#fff",
  },
  listeningLabel: {
    position: "absolute",
    bottom: -16,
    left: 0,
    right: 0,
    textAlign: "center",
    fontSize: 10,
    color: "#F44336",
  },
  errorLabel: {
    position: "absolute",
    bottom: -16,
    left: -20,
    right: -20,
    textAlign: "center",
    fontSize: 10,
    color: "#F44336",
  },
});
