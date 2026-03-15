import { useEffect, useState } from "react";
import { fetchAllQuestions } from "@/api/questions";
import type { QuestionRead } from "@/api/questions";
import QuestionCard from "@/components/QuestionCard";

export default function QuestionsPage() {
  const [questions, setQuestions] = useState<QuestionRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchAllQuestions();
        if (!cancelled) {
          setQuestions(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load questions",
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
  }, []);

  function handleAnswered(updated: QuestionRead) {
    setQuestions((prev) =>
      prev.map((q) => (q.id === updated.id ? updated : q)),
    );
  }

  if (loading) {
    return (
      <div>
        <h1 className="text-2xl font-bold">Pending Questions</h1>
        <p className="mt-4 text-gray-500">Loading questions...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <h1 className="text-2xl font-bold">Pending Questions</h1>
        <p className="mt-4 text-red-600">{error}</p>
      </div>
    );
  }

  if (questions.length === 0) {
    return (
      <div>
        <h1 className="text-2xl font-bold">Pending Questions</h1>
        <p className="mt-4 text-gray-500">
          No pending questions across any session.
        </p>
      </div>
    );
  }

  const unanswered = questions.filter((q) => !q.answered);
  const answered = questions.filter((q) => q.answered);
  const sorted = [...unanswered, ...answered];

  return (
    <div>
      <h1 className="text-2xl font-bold">Pending Questions</h1>
      <div className="mt-4 space-y-3">
        {sorted.map((q) => (
          <QuestionCard
            key={q.id}
            question={q}
            showSessionId
            onAnswered={handleAnswered}
          />
        ))}
      </div>
    </div>
  );
}
