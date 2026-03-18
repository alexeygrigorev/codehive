import { useState } from "react";
import { createCheckpoint } from "@/api/checkpoints";

interface CheckpointCreateProps {
  sessionId: string;
  onCreated?: () => void;
}

export default function CheckpointCreate({
  sessionId,
  onCreated,
}: CheckpointCreateProps) {
  const [label, setLabel] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      setSubmitting(true);
      await createCheckpoint(sessionId, label || undefined);
      setLabel("");
      onCreated?.();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <input
        type="text"
        placeholder="Label (optional)"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        className="rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1 text-sm"
        aria-label="Checkpoint label"
      />
      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-green-500 px-3 py-1 text-sm text-white hover:bg-green-600 disabled:opacity-50"
      >
        Create Checkpoint
      </button>
    </form>
  );
}
