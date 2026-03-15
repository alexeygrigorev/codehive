import { useEffect, useState } from "react";
import { fetchSessionDiffs } from "@/api/diffs";
import type { DiffFileEntry } from "@/api/diffs";

interface ChangedFilesPanelProps {
  sessionId: string;
}

export default function ChangedFilesPanel({
  sessionId,
}: ChangedFilesPanelProps) {
  const [files, setFiles] = useState<DiffFileEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchSessionDiffs(sessionId);
        if (!cancelled) {
          setFiles(data.files);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to fetch diffs",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  if (loading) {
    return <p className="text-gray-500">Loading changed files...</p>;
  }

  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  if (files.length === 0) {
    return <p className="text-gray-500">No changed files</p>;
  }

  return (
    <ul className="space-y-1">
      {files.map((file) => (
        <li
          key={file.path}
          className="flex items-center justify-between rounded border border-gray-200 px-2 py-1.5 text-sm"
        >
          <span className="truncate">{file.path}</span>
          <span className="ml-2 whitespace-nowrap text-xs">
            <span className="text-green-600">+{file.additions}</span>{" "}
            <span className="text-red-600">-{file.deletions}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
