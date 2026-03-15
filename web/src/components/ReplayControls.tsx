import { useCallback, useEffect, useRef, useState } from "react";

interface ReplayControlsProps {
  currentIndex: number;
  totalSteps: number;
  onPrevious: () => void;
  onNext: () => void;
  autoAdvanceInterval?: number;
}

export default function ReplayControls({
  currentIndex,
  totalSteps,
  onPrevious,
  onNext,
  autoAdvanceInterval = 2000,
}: ReplayControlsProps) {
  const [playing, setPlaying] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isFirst = currentIndex <= 0;
  const isLast = currentIndex >= totalSteps - 1;

  const stopPlaying = useCallback(() => {
    setPlaying(false);
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const togglePlay = useCallback(() => {
    if (playing) {
      stopPlaying();
    } else {
      setPlaying(true);
    }
  }, [playing, stopPlaying]);

  // Auto-advance effect
  useEffect(() => {
    if (!playing) return;

    if (isLast) {
      stopPlaying();
      return;
    }

    intervalRef.current = setInterval(() => {
      onNext();
    }, autoAdvanceInterval);

    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [playing, isLast, onNext, autoAdvanceInterval, stopPlaying]);

  return (
    <div className="replay-controls flex items-center gap-3 p-2">
      <button
        type="button"
        className="rounded bg-gray-200 px-3 py-1 text-sm disabled:opacity-50"
        onClick={onPrevious}
        disabled={isFirst}
        aria-label="Previous"
      >
        Previous
      </button>
      <button
        type="button"
        className="rounded bg-blue-500 px-3 py-1 text-sm text-white"
        onClick={togglePlay}
        aria-label={playing ? "Pause" : "Play"}
      >
        {playing ? "Pause" : "Play"}
      </button>
      <button
        type="button"
        className="rounded bg-gray-200 px-3 py-1 text-sm disabled:opacity-50"
        onClick={onNext}
        disabled={isLast}
        aria-label="Next"
      >
        Next
      </button>
      <span className="step-indicator text-sm text-gray-600">
        Step {totalSteps === 0 ? 0 : currentIndex + 1} of {totalSteps}
      </span>
    </div>
  );
}
