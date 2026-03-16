import { useCallback, useEffect, useRef, useState } from "react";
import Voice, {
  type SpeechResultsEvent,
  type SpeechErrorEvent,
} from "@react-native-voice/voice";

export interface UseVoiceRecognitionResult {
  isListening: boolean;
  transcript: string;
  error: string | null;
  isAvailable: boolean;
  startListening: () => Promise<void>;
  stopListening: () => Promise<void>;
  resetTranscript: () => void;
}

export function useVoiceRecognition(): UseVoiceRecognitionResult {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isAvailable, setIsAvailable] = useState(true);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    Voice.isAvailable()
      .then((available) => {
        if (mountedRef.current) {
          setIsAvailable(!!available);
        }
      })
      .catch(() => {
        if (mountedRef.current) {
          setIsAvailable(false);
        }
      });

    const onSpeechResults = (e: SpeechResultsEvent) => {
      if (!mountedRef.current) return;
      const text = e.value?.[0] ?? "";
      if (text) {
        setTranscript(text);
      }
    };

    const onSpeechError = (e: SpeechErrorEvent) => {
      if (!mountedRef.current) return;
      setError(e.error?.message ?? "Speech recognition error");
      setIsListening(false);
    };

    Voice.onSpeechResults = onSpeechResults;
    Voice.onSpeechError = onSpeechError;

    return () => {
      mountedRef.current = false;
      Voice.destroy().then(Voice.removeAllListeners);
    };
  }, []);

  const startListening = useCallback(async () => {
    setError(null);
    setTranscript("");
    try {
      await Voice.start("en-US");
      setIsListening(true);
    } catch (_e) {
      setError("Failed to start speech recognition");
    }
  }, []);

  const stopListening = useCallback(async () => {
    try {
      await Voice.stop();
      setIsListening(false);
    } catch (_e) {
      setError("Failed to stop speech recognition");
    }
  }, []);

  const resetTranscript = useCallback(() => {
    setTranscript("");
    setError(null);
  }, []);

  return {
    isListening,
    transcript,
    error,
    isAvailable,
    startListening,
    stopListening,
    resetTranscript,
  };
}
