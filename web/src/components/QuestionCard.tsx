import { useState } from "react";
import { answerQuestion } from "@/api/questions";
import type { QuestionRead } from "@/api/questions";

function formatRelativeTime(dateString: string): string {
  const now = Date.now();
  const then = new Date(dateString).getTime();
  const diffMs = now - then;
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return "just now";
  if (diffMinutes < 60)
    return `${diffMinutes} minute${diffMinutes === 1 ? "" : "s"} ago`;
  if (diffHours < 24)
    return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;
  return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`;
}

interface QuestionCardProps {
  question: QuestionRead;
  showSessionId?: boolean;
  onAnswered?: (updated: QuestionRead) => void;
}

export default function QuestionCard({
  question,
  showSessionId,
  onAnswered,
}: QuestionCardProps) {
  const [answerText, setAnswerText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [localQuestion, setLocalQuestion] = useState(question);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!answerText.trim()) return;

    setSubmitting(true);
    setError(null);
    try {
      const updated = await answerQuestion(
        localQuestion.session_id,
        localQuestion.id,
        answerText.trim(),
      );
      setLocalQuestion(updated);
      onAnswered?.(updated);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to submit answer",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded border border-gray-200 dark:border-gray-700 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span
          className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${
            localQuestion.answered
              ? "bg-green-100 text-green-800"
              : "bg-yellow-100 text-yellow-800"
          }`}
        >
          {localQuestion.answered ? "Answered" : "Unanswered"}
        </span>
        <span className="text-xs text-gray-400">
          {formatRelativeTime(localQuestion.created_at)}
        </span>
      </div>

      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
        {localQuestion.question}
      </p>

      {localQuestion.context && (
        <p className="mt-1 text-xs text-gray-500">{localQuestion.context}</p>
      )}

      {showSessionId && (
        <p className="mt-1 text-xs text-gray-400">
          Session: {localQuestion.session_id}
        </p>
      )}

      {localQuestion.answered && localQuestion.answer && (
        <div className="mt-2 rounded bg-gray-50 dark:bg-gray-800 p-2">
          <p className="text-sm text-gray-700 dark:text-gray-300">{localQuestion.answer}</p>
        </div>
      )}

      {!localQuestion.answered && (
        <form onSubmit={handleSubmit} className="mt-2">
          <textarea
            className="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 p-2 text-sm"
            rows={2}
            placeholder="Type your answer..."
            value={answerText}
            onChange={(e) => setAnswerText(e.target.value)}
            disabled={submitting}
          />
          <button
            type="submit"
            disabled={!answerText.trim() || submitting}
            className="mt-1 rounded bg-blue-500 px-3 py-1 text-sm text-white disabled:opacity-50"
          >
            {submitting ? "Submitting..." : "Submit Answer"}
          </button>
        </form>
      )}

      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}
