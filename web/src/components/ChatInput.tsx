import { useState, useCallback, useEffect, useRef } from "react";
import type { KeyboardEvent } from "react";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { useAudioWaveform } from "@/hooks/useAudioWaveform";
import VoiceButton from "@/components/VoiceButton";
import TranscriptPreview from "@/components/TranscriptPreview";
import RecordingOverlay from "@/components/RecordingOverlay";

export interface ChatInputProps {
  onSend: (content: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState("");
  const {
    isListening,
    transcript,
    isSupported,
    startListening,
    stopListening,
    resetTranscript,
  } = useVoiceInput();

  const {
    start: startWaveform,
    stop: stopWaveform,
    waveformData,
    elapsedSeconds,
  } = useAudioWaveform();

  const [isProcessing, setIsProcessing] = useState(false);
  const wasListeningRef = useRef(false);

  const showTranscriptPreview =
    !isListening && !isProcessing && transcript.length > 0;

  // Track transitions from listening to not-listening for processing state
  useEffect(() => {
    if (wasListeningRef.current && !isListening) {
      // Just stopped listening - show processing briefly
      setIsProcessing(true);
      const timer = setTimeout(() => {
        setIsProcessing(false);
      }, 1500);
      return () => clearTimeout(timer);
    }
    wasListeningRef.current = isListening;
  }, [isListening]);

  const handleStartListening = useCallback(() => {
    startListening();
    startWaveform();
  }, [startListening, startWaveform]);

  const handleStopListening = useCallback(() => {
    stopListening();
    stopWaveform();
  }, [stopListening, stopWaveform]);

  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText("");
  }, [text, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleTranscriptSend = useCallback(
    (transcriptText: string) => {
      const trimmed = transcriptText.trim();
      if (trimmed) {
        onSend(trimmed);
      }
      resetTranscript();
    },
    [onSend, resetTranscript],
  );

  const handleTranscriptDiscard = useCallback(() => {
    resetTranscript();
  }, [resetTranscript]);

  return (
    <div className="border-t border-gray-200 bg-white p-4">
      {showTranscriptPreview && (
        <div className="mb-2">
          <TranscriptPreview
            transcript={transcript}
            onSend={handleTranscriptSend}
            onDiscard={handleTranscriptDiscard}
          />
        </div>
      )}
      {(isListening || isProcessing) && (
        <div className="mb-2">
          <RecordingOverlay
            waveformData={waveformData}
            elapsedSeconds={elapsedSeconds}
            isProcessing={isProcessing}
            onStop={handleStopListening}
          />
        </div>
      )}
      <div className="flex gap-2">
        {!isListening && !isProcessing && (
          <textarea
            className="flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            placeholder="Type a message..."
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            aria-label="Message input"
          />
        )}
        <VoiceButton
          isListening={isListening}
          isSupported={isSupported}
          onStartListening={handleStartListening}
          onStopListening={handleStopListening}
        />
        <button
          type="button"
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={handleSend}
          disabled={disabled}
        >
          Send
        </button>
      </div>
    </div>
  );
}
