import type { DiffFile } from "@/utils/parseDiff";

interface DiffViewerProps {
  diffFile: DiffFile | null;
}

export default function DiffViewer({ diffFile }: DiffViewerProps) {
  if (!diffFile || diffFile.hunks.length === 0) {
    return <div className="p-4 text-gray-500">No changes</div>;
  }

  return (
    <div className="font-mono text-sm overflow-x-auto">
      <div className="px-4 py-2 bg-gray-100 font-semibold border-b">
        {diffFile.path}
      </div>
      {diffFile.hunks.map((hunk, hunkIdx) => (
        <div key={hunkIdx}>
          <div className="px-4 py-1 bg-gray-50 text-gray-500 text-xs border-b">
            @@ -{hunk.oldStart},{hunk.oldCount} +{hunk.newStart},{hunk.newCount} @@
          </div>
          {hunk.lines.map((line, lineIdx) => {
            let bgClass = "";
            let prefix = " ";
            if (line.type === "addition") {
              bgClass = "bg-green-50 text-green-900";
              prefix = "+";
            } else if (line.type === "deletion") {
              bgClass = "bg-red-50 text-red-900";
              prefix = "-";
            }

            return (
              <div
                key={`${hunkIdx}-${lineIdx}`}
                className={`flex border-b border-gray-100 ${bgClass}`}
              >
                <span className="w-12 text-right pr-2 text-gray-400 select-none flex-shrink-0">
                  {line.oldLineNumber ?? ""}
                </span>
                <span className="w-12 text-right pr-2 text-gray-400 select-none flex-shrink-0">
                  {line.newLineNumber ?? ""}
                </span>
                <span className="px-2 whitespace-pre">
                  {prefix}{line.content}
                </span>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
