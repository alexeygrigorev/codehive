import AudioWaveform from "@/components/AudioWaveform";

export interface RecordingOverlayProps {
  waveformData: Uint8Array | null;
  elapsedSeconds: number;
  isProcessing: boolean;
  onStop: () => void;
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export default function RecordingOverlay({
  waveformData,
  elapsedSeconds,
  isProcessing,
  onStop,
}: RecordingOverlayProps) {
  if (isProcessing) {
    return (
      <div
        className="flex items-center justify-center gap-2 rounded-lg border border-gray-300 bg-gray-50 px-3 py-3"
        data-testid="processing-indicator"
      >
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
        <span className="text-sm text-gray-600">Processing...</span>
      </div>
    );
  }

  return (
    <div
      className="flex items-center gap-3 rounded-lg border border-red-300 bg-red-50 px-3 py-2"
      data-testid="recording-overlay"
    >
      <span className="inline-block h-3 w-3 rounded-full bg-red-600 animate-pulse" />
      <div className="flex-1">
        <AudioWaveform waveformData={waveformData} height={48} />
      </div>
      <span
        className="text-sm font-mono text-gray-700 min-w-[3rem] text-right"
        data-testid="elapsed-timer"
      >
        {formatTime(elapsedSeconds)}
      </span>
      <button
        type="button"
        className="rounded-lg bg-red-600 px-3 py-1 text-sm font-medium text-white hover:bg-red-700"
        onClick={onStop}
        aria-label="Stop recording"
      >
        Stop
      </button>
    </div>
  );
}
