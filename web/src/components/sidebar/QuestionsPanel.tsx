import { useEffect, useState } from "react";
import { fetchSessionQuestions } from "@/api/questions";
import type { QuestionRead } from "@/api/questions";
import QuestionCard from "@/components/QuestionCard";

interface QuestionsPanelProps {
  sessionId: string;
}

export default function QuestionsPanel({ sessionId }: QuestionsPanelProps) {
  const [questions, setQuestions] = useState<QuestionRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchSessionQuestions(sessionId);
        if (!cancelled) {
          setQuestions(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to fetch questions",
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

  function handleAnswered(updated: QuestionRead) {
    setQuestions((prev) =>
      prev.map((q) => (q.id === updated.id ? updated : q)),
    );
  }

  if (loading) {
    return <p className="text-gray-500">Loading questions...</p>;
  }

  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  if (questions.length === 0) {
    return <p className="text-gray-500">No pending questions</p>;
  }

  const unanswered = questions.filter((q) => !q.answered);
  const answered = questions.filter((q) => q.answered);
  const sorted = [...unanswered, ...answered];

  return (
    <div className="space-y-3">
      {sorted.map((q) => (
        <QuestionCard key={q.id} question={q} onAnswered={handleAnswered} />
      ))}
    </div>
  );
}
