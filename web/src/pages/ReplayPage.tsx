import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import type { ReplayStep as ReplayStepData } from "@/api/replay";
import { fetchReplay } from "@/api/replay";
import ReplayControls from "@/components/ReplayControls";
import ReplayTimeline from "@/components/ReplayTimeline";
import ReplayStepComponent from "@/components/ReplayStep";

export default function ReplayPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [steps, setSteps] = useState<ReplayStepData[]>([]);
  const [totalSteps, setTotalSteps] = useState(0);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;

    async function load() {
      try {
        // Fetch all steps (up to 200 at once for replay)
        const data = await fetchReplay(sessionId!, 200, 0);
        if (!cancelled) {
          setSteps(data.steps);
          setTotalSteps(data.total_steps);
          setCurrentIndex(0);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load replay",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const handlePrevious = useCallback(() => {
    setCurrentIndex((prev) => Math.max(0, prev - 1));
  }, []);

  const handleNext = useCallback(() => {
    setCurrentIndex((prev) => Math.min(totalSteps - 1, prev + 1));
  }, [totalSteps]);

  const handleStepClick = useCallback((index: number) => {
    setCurrentIndex(index);
  }, []);

  if (loading) {
    return (
      <div>
        <h1 className="text-2xl font-bold dark:text-gray-100">Session Replay</h1>
        <p className="text-gray-500 mt-4">Loading replay...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <h1 className="text-2xl font-bold dark:text-gray-100">Session Replay</h1>
        <p className="text-red-600 mt-4">{error}</p>
      </div>
    );
  }

  const currentStep = steps.find((s) => s.index === currentIndex);

  return (
    <div className="replay-page flex h-full flex-col">
      <div className="border-b border-gray-200 dark:border-gray-700 px-4 py-3">
        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Session Replay</h1>
      </div>
      <ReplayTimeline
        steps={steps}
        currentIndex={currentIndex}
        onStepClick={handleStepClick}
      />
      <div className="flex-1 overflow-y-auto p-4">
        {currentStep ? (
          <ReplayStepComponent step={currentStep} />
        ) : (
          <p className="text-gray-500">No steps to display</p>
        )}
      </div>
      <div className="border-t border-gray-200 dark:border-gray-700">
        <ReplayControls
          currentIndex={currentIndex}
          totalSteps={totalSteps}
          onPrevious={handlePrevious}
          onNext={handleNext}
        />
      </div>
    </div>
  );
}
