export default function ThinkingIndicator() {
  return (
    <div
      className="mr-auto max-w-[80%] rounded-lg bg-gray-100 px-4 py-3 dark:bg-gray-700"
      data-testid="thinking-indicator"
    >
      <div className="flex items-center gap-1">
        <span
          className="inline-block h-2 w-2 animate-bounce rounded-full bg-gray-400 dark:bg-gray-400"
          style={{ animationDelay: "0ms", animationDuration: "1s" }}
        />
        <span
          className="inline-block h-2 w-2 animate-bounce rounded-full bg-gray-400 dark:bg-gray-400"
          style={{ animationDelay: "150ms", animationDuration: "1s" }}
        />
        <span
          className="inline-block h-2 w-2 animate-bounce rounded-full bg-gray-400 dark:bg-gray-400"
          style={{ animationDelay: "300ms", animationDuration: "1s" }}
        />
      </div>
    </div>
  );
}
