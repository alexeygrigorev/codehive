export interface VoiceButtonProps {
  isListening: boolean;
  isSupported: boolean;
  onStartListening: () => void;
  onStopListening: () => void;
}

export default function VoiceButton({
  isListening,
  isSupported,
  onStartListening,
  onStopListening,
}: VoiceButtonProps) {
  if (!isSupported) {
    return null;
  }

  return (
    <button
      type="button"
      className={`rounded-lg px-3 py-2 text-sm font-medium ${
        isListening
          ? "bg-red-600 text-white animate-pulse voice-recording"
          : "bg-gray-200 text-gray-700 hover:bg-gray-300"
      }`}
      onClick={isListening ? onStopListening : onStartListening}
      aria-label={isListening ? "Stop voice input" : "Start voice input"}
    >
      {isListening ? "Stop" : "Mic"}
    </button>
  );
}
