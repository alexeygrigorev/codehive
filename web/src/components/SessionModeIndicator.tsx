export const SESSION_MODES = [
  "brainstorm",
  "interview",
  "planning",
  "execution",
  "review",
] as const;

export type SessionMode = (typeof SESSION_MODES)[number];

export const MODE_STYLES: Record<string, string> = {
  brainstorm: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  interview: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200",
  planning: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  execution: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  review: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
};

const DEFAULT_STYLE = "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300";

export interface SessionModeIndicatorProps {
  mode: string;
}

export default function SessionModeIndicator({
  mode,
}: SessionModeIndicatorProps) {
  const style = MODE_STYLES[mode] ?? DEFAULT_STYLE;

  return (
    <span
      className={`mode-indicator inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${style}`}
    >
      {mode}
    </span>
  );
}
