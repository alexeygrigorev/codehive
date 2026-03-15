export interface ToolCallResultProps {
  toolName: string;
  input?: string;
  output?: string;
  isError?: boolean;
  finished?: boolean;
}

export default function ToolCallResult({
  toolName,
  input,
  output,
  isError,
  finished,
}: ToolCallResultProps) {
  const borderColor = isError
    ? "border-red-400 bg-red-50"
    : finished
      ? "border-green-400 bg-green-50"
      : "border-yellow-400 bg-yellow-50";

  return (
    <div
      className={`tool-call-result mr-auto max-w-[80%] rounded-lg border-l-4 px-4 py-2 text-sm ${borderColor}`}
      data-tool={toolName}
    >
      <div className="font-semibold text-gray-700">
        Tool: <span className="font-mono">{toolName}</span>
      </div>
      {input && (
        <div className="mt-1 text-gray-500 text-xs truncate">
          Input: {input}
        </div>
      )}
      {!finished && (
        <div className="tool-running mt-1 text-yellow-700">Running...</div>
      )}
      {finished && output && (
        <div
          className={`tool-output mt-1 font-mono text-xs whitespace-pre-wrap ${isError ? "text-red-700" : "text-gray-700"}`}
        >
          {output}
        </div>
      )}
      {finished && isError && (
        <span className="tool-error text-xs text-red-600 font-medium">
          Error
        </span>
      )}
    </div>
  );
}
