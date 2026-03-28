import { useEffect, useState } from "react";
import {
  fetchContextFiles,
  fetchContextFileContent,
  type ContextFileEntry,
} from "@/api/contextFiles";

interface ContextFilesSectionProps {
  projectId: string;
}

export default function ContextFilesSection({
  projectId,
}: ContextFilesSectionProps) {
  const [files, setFiles] = useState<ContextFileEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [contentLoading, setContentLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await fetchContextFiles(projectId);
        if (!cancelled) setFiles(result);
      } catch (err) {
        if (!cancelled)
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load context files",
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  async function handleFileClick(filePath: string) {
    if (selectedFile === filePath) {
      setSelectedFile(null);
      setFileContent(null);
      return;
    }
    setSelectedFile(filePath);
    setFileContent(null);
    setContentLoading(true);
    try {
      const result = await fetchContextFileContent(projectId, filePath);
      setFileContent(result.content);
    } catch (err) {
      setFileContent(
        err instanceof Error ? err.message : "Failed to load file content",
      );
    } finally {
      setContentLoading(false);
    }
  }

  if (loading) {
    return (
      <div data-testid="context-files-section" className="mt-4">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          Context Files
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Loading...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="context-files-section" className="mt-4">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          Context Files
        </h3>
        <p className="text-sm text-red-600 mt-1">{error}</p>
      </div>
    );
  }

  return (
    <div data-testid="context-files-section" className="mt-4">
      <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
        Context Files
      </h3>
      {files.length === 0 ? (
        <p
          className="text-sm text-gray-500 dark:text-gray-400 mt-1"
          data-testid="no-context-files"
        >
          No context files detected
        </p>
      ) : (
        <ul className="mt-2 space-y-1" data-testid="context-file-list">
          {files.map((f) => (
            <li key={f.path}>
              <button
                onClick={() => handleFileClick(f.path)}
                className={`text-sm font-mono px-2 py-1 rounded w-full text-left hover:bg-gray-100 dark:hover:bg-gray-700 ${
                  selectedFile === f.path
                    ? "bg-gray-100 dark:bg-gray-700 text-blue-600 dark:text-blue-400"
                    : "text-gray-700 dark:text-gray-300"
                }`}
                data-testid="context-file-item"
              >
                {f.path}
              </button>
              {selectedFile === f.path && (
                <div
                  className="mt-1 ml-2 p-3 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded text-sm"
                  data-testid="context-file-preview"
                >
                  {contentLoading ? (
                    <p className="text-gray-500 dark:text-gray-400">
                      Loading...
                    </p>
                  ) : (
                    <pre className="whitespace-pre-wrap font-mono text-gray-800 dark:text-gray-200 overflow-x-auto">
                      {fileContent}
                    </pre>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
