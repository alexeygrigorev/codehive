import { useTheme } from "@/context/ThemeContext";
import type { Theme } from "@/context/ThemeContext";

const CYCLE: Theme[] = ["light", "dark", "system"];

const LABELS: Record<Theme, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
};

const ICONS: Record<Theme, string> = {
  light: "Sun",
  dark: "Moon",
  system: "Auto",
};

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  function handleClick() {
    const currentIndex = CYCLE.indexOf(theme);
    const nextIndex = (currentIndex + 1) % CYCLE.length;
    setTheme(CYCLE[nextIndex]);
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className="theme-toggle rounded-md px-2 py-1 text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
      aria-label={`Theme: ${LABELS[theme]}. Click to change.`}
      data-testid="theme-toggle"
    >
      {ICONS[theme]}
    </button>
  );
}
