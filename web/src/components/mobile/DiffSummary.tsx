export interface DiffSummaryFile {
  path: string;
  additions: number;
  deletions: number;
}

export interface DiffSummaryProps {
  files: DiffSummaryFile[];
  onFileClick?: (path: string) => void;
}

export default function DiffSummary({ files, onFileClick }: DiffSummaryProps) {
  if (files.length === 0) {
    return (
      <div
        className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-500"
        data-testid="diff-summary"
      >
        No changes
      </div>
    );
  }

  const totalAdditions = files.reduce((sum, f) => sum + f.additions, 0);
  const totalDeletions = files.reduce((sum, f) => sum + f.deletions, 0);

  return (
    <div
      className="rounded-lg border border-gray-200 bg-white p-4"
      data-testid="diff-summary"
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-gray-700">
          {files.length} {files.length === 1 ? "file" : "files"} changed
        </span>
        <span className="text-xs">
          <span className="text-green-600 font-medium">+{totalAdditions}</span>
          {" / "}
          <span className="text-red-600 font-medium">-{totalDeletions}</span>
        </span>
      </div>
      <ul className="space-y-1">
        {files.map((file) => (
          <li key={file.path}>
            <button
              type="button"
              className="w-full text-left text-sm font-mono truncate text-blue-600 hover:underline"
              style={{ minHeight: "44px" }}
              onClick={() => onFileClick?.(file.path)}
            >
              {file.path}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
