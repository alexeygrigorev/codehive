import { useEffect } from "react";
import type { DiffFile } from "@/utils/parseDiff";
import DiffViewer from "./DiffViewer";

interface DiffModalProps {
  isOpen: boolean;
  onClose: () => void;
  diffFile: DiffFile | null;
}

export default function DiffModal({ isOpen, onClose, diffFile }: DiffModalProps) {
  useEffect(() => {
    if (!isOpen) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      data-testid="diff-modal-overlay"
    >
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-full h-full max-w-full max-h-full overflow-auto">
        <div className="flex items-center justify-between px-4 py-3 border-b dark:border-gray-700">
          <h2 className="text-lg font-semibold dark:text-gray-100">
            {diffFile?.path ?? "Diff Viewer"}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 text-xl leading-none"
            aria-label="Close"
          >
            &times;
          </button>
        </div>
        <div className="p-0">
          <DiffViewer diffFile={diffFile} />
        </div>
      </div>
    </div>
  );
}
