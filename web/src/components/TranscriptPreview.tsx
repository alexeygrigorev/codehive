import { useState } from "react";

export interface TranscriptPreviewProps {
  transcript: string;
  onSend: (text: string) => void;
  onDiscard: () => void;
}

export default function TranscriptPreview({
  transcript,
  onSend,
  onDiscard,
}: TranscriptPreviewProps) {
  const [editedText, setEditedText] = useState(transcript);

  return (
    <div className="flex flex-col gap-2 border border-gray-300 rounded-lg bg-gray-50 p-3">
      <textarea
        className="w-full resize-none rounded border border-gray-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        value={editedText}
        onChange={(e) => setEditedText(e.target.value)}
        rows={3}
        aria-label="Voice transcript"
      />
      <div className="flex gap-2 justify-end">
        <button
          type="button"
          className="rounded-lg bg-gray-200 px-3 py-1 text-sm font-medium text-gray-700 hover:bg-gray-300"
          onClick={onDiscard}
        >
          Discard
        </button>
        <button
          type="button"
          className="rounded-lg bg-blue-600 px-3 py-1 text-sm font-medium text-white hover:bg-blue-700"
          onClick={() => onSend(editedText)}
        >
          Send
        </button>
      </div>
    </div>
  );
}
