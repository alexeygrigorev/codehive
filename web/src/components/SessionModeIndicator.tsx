export const SESSION_MODES = [
  "brainstorm",
  "interview",
  "planning",
  "execution",
  "review",
] as const;

export type SessionMode = (typeof SESSION_MODES)[number];

export const MODE_STYLES: Record<string, string> = {
  brainstorm: "bg-purple-100 text-purple-800",
  interview: "bg-cyan-100 text-cyan-800",
  planning: "bg-yellow-100 text-yellow-800",
  execution: "bg-blue-100 text-blue-800",
  review: "bg-green-100 text-green-800",
};

const DEFAULT_STYLE = "bg-gray-100 text-gray-700";

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
