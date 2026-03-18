import type { ReplayStep } from "@/api/replay";

interface ReplayTimelineProps {
  steps: ReplayStep[];
  currentIndex: number;
  onStepClick: (index: number) => void;
}

const stepTypeLabels: Record<string, string> = {
  message: "MSG",
  tool_call_start: "TOOL",
  tool_call_finish: "DONE",
  file_change: "FILE",
  task_started: "TASK",
  task_completed: "TASK",
  session_status_change: "STS",
};

export default function ReplayTimeline({
  steps,
  currentIndex,
  onStepClick,
}: ReplayTimelineProps) {
  return (
    <div className="replay-timeline flex gap-1 overflow-x-auto p-2">
      {steps.map((step) => {
        const isCurrent = step.index === currentIndex;
        const label = stepTypeLabels[step.step_type] ?? "EVT";

        return (
          <button
            key={step.index}
            type="button"
            className={`timeline-marker flex-shrink-0 rounded px-2 py-1 text-xs font-mono cursor-pointer transition-colors ${
              isCurrent
                ? "bg-blue-600 text-white"
                : "bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600"
            }`}
            onClick={() => onStepClick(step.index)}
            aria-label={`Step ${step.index + 1}: ${step.step_type}`}
            data-step-index={step.index}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
