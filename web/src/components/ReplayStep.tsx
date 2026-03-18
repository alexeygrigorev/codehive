import type { ReplayStep as ReplayStepData } from "@/api/replay";
import MessageBubble from "./MessageBubble";
import ToolCallResult from "./ToolCallResult";

interface ReplayStepProps {
  step: ReplayStepData;
}

export default function ReplayStep({ step }: ReplayStepProps) {
  switch (step.step_type) {
    case "message":
      return (
        <MessageBubble
          role={(step.data.role as string) ?? "assistant"}
          content={(step.data.content as string) ?? ""}
        />
      );

    case "tool_call_start":
      return (
        <ToolCallResult
          toolName={(step.data.tool as string) ?? "unknown"}
          input={step.data.input as string | undefined}
          finished={false}
        />
      );

    case "tool_call_finish":
      return (
        <ToolCallResult
          toolName={(step.data.tool as string) ?? "unknown"}
          input={step.data.input as string | undefined}
          output={(step.data.output as string) ?? ""}
          isError={!!step.data.is_error}
          finished={true}
        />
      );

    case "file_change":
      return (
        <div className="replay-file-change mr-auto max-w-[80%] rounded-lg border-l-4 border-indigo-400 bg-indigo-50 dark:bg-indigo-900/30 px-4 py-2 text-sm">
          <div className="font-semibold text-indigo-700 dark:text-indigo-300">File Change</div>
          <div className="mt-1 font-mono text-xs text-gray-700 dark:text-gray-300">
            <span className="file-path">
              {(step.data.path as string) ?? "unknown"}
            </span>
            {typeof step.data.action === "string" && (
              <span className="ml-2 text-indigo-600 dark:text-indigo-400">
                ({step.data.action as string})
              </span>
            )}
          </div>
          {typeof step.data.diff === "string" && (
            <pre className="file-diff mt-2 overflow-x-auto whitespace-pre-wrap text-xs text-gray-600">
              {step.data.diff as string}
            </pre>
          )}
        </div>
      );

    default:
      return (
        <div className="replay-unknown mr-auto max-w-[80%] rounded-lg border-l-4 border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 px-4 py-2 text-sm">
          <div className="font-semibold text-gray-600 dark:text-gray-400">
            {step.step_type}
          </div>
          <pre className="json-view mt-1 overflow-x-auto whitespace-pre-wrap text-xs text-gray-500">
            {JSON.stringify(step.data, null, 2)}
          </pre>
        </div>
      );
  }
}
