export interface ToolCallResultProps {
  toolName: string;
  input?: Record<string, unknown> | string;
  output?: string;
  isError?: boolean;
  finished?: boolean;
}

function truncate(value: string, maxLen = 120): string {
  if (value.length <= maxLen) return value;
  return value.slice(0, maxLen) + "...";
}

function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

export default function ToolCallResult({
  toolName,
  input,
  output,
  isError,
  finished,
}: ToolCallResultProps) {
  const borderColor = isError
    ? "border-red-400 bg-red-50 dark:bg-red-950/40"
    : finished
      ? "border-green-400 bg-green-50 dark:bg-green-950/40"
      : "border-yellow-400 bg-yellow-50 dark:bg-yellow-950/40";

  return (
    <div
      className={`tool-call-result mr-auto max-w-[80%] rounded-lg border-l-4 px-4 py-2 text-sm ${borderColor}`}
      data-tool={toolName}
      data-testid="tool-call-card"
    >
      {/* Header row: icon + name + spinner + error badge */}
      <div className="flex items-center gap-2">
        <span className="text-base" aria-hidden="true">
          🔧
        </span>
        <span className="font-mono font-bold text-gray-800 dark:text-gray-200">
          {toolName}
        </span>
        {!finished && (
          <span
            className="tool-spinner inline-block h-4 w-4 animate-spin rounded-full border-2 border-yellow-400 border-t-transparent dark:border-yellow-500 dark:border-t-transparent"
            role="status"
            aria-label="Running"
          />
        )}
        {isError && (
          <span className="tool-error rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700 dark:bg-red-900/60 dark:text-red-300">
            Error
          </span>
        )}
      </div>

      {/* Parameters section */}
      {input && (
        <div className="tool-params mt-2 space-y-0.5 text-xs text-gray-600 dark:text-gray-400">
          {typeof input === "object" ? (
            Object.entries(input).map(([key, value]) => (
              <div key={key} className="tool-param">
                <span className="font-semibold text-gray-700 dark:text-gray-300">
                  {key}:
                </span>{" "}
                <span className="font-mono">
                  {truncate(formatValue(value))}
                </span>
              </div>
            ))
          ) : (
            <div className="tool-param font-mono">{truncate(input)}</div>
          )}
        </div>
      )}

      {/* Result section - collapsible */}
      {finished && output && (
        <details
          className="tool-result mt-2"
          open={isError ? true : undefined}
        >
          <summary className="cursor-pointer select-none text-xs font-medium text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200">
            Result
          </summary>
          <pre
            className={`tool-output mt-1 max-h-60 overflow-auto rounded border p-2 font-mono text-xs whitespace-pre-wrap border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900 ${
              isError
                ? "text-red-700 dark:text-red-400"
                : "text-gray-700 dark:text-gray-300"
            }`}
          >
            {output}
          </pre>
        </details>
      )}
    </div>
  );
}
