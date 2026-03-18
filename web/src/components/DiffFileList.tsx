import type { DiffFileEntry } from "@/api/diffs";

interface DiffFileListProps {
  files: DiffFileEntry[];
  selectedPath?: string;
  onSelectFile: (path: string) => void;
}

export default function DiffFileList({
  files,
  selectedPath,
  onSelectFile,
}: DiffFileListProps) {
  if (files.length === 0) {
    return <div className="p-4 text-gray-500 dark:text-gray-400">No changed files</div>;
  }

  return (
    <ul className="divide-y divide-gray-200 dark:divide-gray-700">
      {files.map((file) => (
        <li
          key={file.path}
          role="button"
          tabIndex={0}
          className={`px-4 py-2 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 ${
            selectedPath === file.path ? "bg-blue-50 dark:bg-blue-900/30" : ""
          }`}
          onClick={() => onSelectFile(file.path)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              onSelectFile(file.path);
            }
          }}
        >
          <div className="flex items-center justify-between">
            <span className="font-mono text-sm truncate">{file.path}</span>
            <span className="text-xs ml-2 flex-shrink-0">
              <span className="text-green-600">+{file.additions}</span>
              {" / "}
              <span className="text-red-600">-{file.deletions}</span>
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}
