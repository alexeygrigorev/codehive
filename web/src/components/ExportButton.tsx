import { useState, useRef, useEffect, useCallback } from "react";
import { downloadTranscript } from "@/api/transcript";

export interface ExportButtonProps {
  sessionId?: string;
  sessionName?: string;
}

export default function ExportButton({
  sessionId,
  sessionName,
}: ExportButtonProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleExport = useCallback(
    async (format: "json" | "markdown") => {
      if (!sessionId) return;
      setLoading(true);
      setOpen(false);
      try {
        await downloadTranscript(sessionId, format, sessionName);
      } catch {
        // Error handling can be extended later
      } finally {
        setLoading(false);
      }
    },
    [sessionId, sessionName],
  );

  return (
    <div ref={dropdownRef} className="relative inline-block">
      <button
        type="button"
        className="rounded-lg bg-gray-200 dark:bg-gray-700 px-3 py-1 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50"
        disabled={!sessionId || loading}
        onClick={() => setOpen((prev) => !prev)}
        aria-label="Export transcript"
      >
        {loading ? "Exporting..." : "Export"}
      </button>
      {open && (
        <div className="absolute right-0 z-10 mt-1 w-48 rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5">
          <button
            type="button"
            className="block w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
            onClick={() => handleExport("markdown")}
          >
            Export as Markdown
          </button>
          <button
            type="button"
            className="block w-full px-4 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
            onClick={() => handleExport("json")}
          >
            Export as JSON
          </button>
        </div>
      )}
    </div>
  );
}
