import { SESSION_MODES, MODE_STYLES } from "./SessionModeIndicator";

export interface SessionModeSwitcherProps {
  currentMode: string;
  onModeChange: (mode: string) => void;
  disabled?: boolean;
  loading?: boolean;
}

export default function SessionModeSwitcher({
  currentMode,
  onModeChange,
  disabled = false,
  loading = false,
}: SessionModeSwitcherProps) {
  const isDisabled = disabled || loading;

  return (
    <div className="mode-switcher flex gap-1" role="group" aria-label="Session mode">
      {SESSION_MODES.map((mode) => {
        const isActive = mode === currentMode;
        const modeStyle = MODE_STYLES[mode] ?? "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300";
        const activeClass = isActive ? `${modeStyle} ring-2 ring-offset-1 dark:ring-offset-gray-900` : "bg-gray-50 dark:bg-gray-700 text-gray-500 dark:text-gray-400";

        return (
          <button
            key={mode}
            type="button"
            className={`mode-option rounded-full px-2.5 py-0.5 text-xs font-medium ${activeClass} ${isDisabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer hover:opacity-80"}`}
            disabled={isDisabled}
            aria-pressed={isActive}
            onClick={() => {
              if (!isActive && !isDisabled) {
                onModeChange(mode);
              }
            }}
          >
            {mode}
          </button>
        );
      })}
      {loading && (
        <span className="mode-loading text-xs text-gray-400 self-center ml-1">
          Saving...
        </span>
      )}
    </div>
  );
}
