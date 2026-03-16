import { useState } from "react";
import {
  respondToFlow,
  type FlowQuestion,
  type FlowAnswer,
  type ProjectBrief,
} from "@/api/projectFlow";

interface FlowChatProps {
  flowId: string;
  questions: FlowQuestion[];
  onBriefReady: (brief: ProjectBrief) => void;
}

export default function FlowChat({
  flowId,
  questions,
  onBriefReady,
}: FlowChatProps) {
  const [currentQuestions, setCurrentQuestions] =
    useState<FlowQuestion[]>(questions);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allAnswered = currentQuestions.every(
    (q) => (answers[q.id] ?? "").trim() !== "",
  );

  function handleAnswerChange(questionId: string, value: string) {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  }

  async function handleSubmit() {
    setLoading(true);
    setError(null);
    try {
      const flowAnswers: FlowAnswer[] = currentQuestions.map((q) => ({
        question_id: q.id,
        answer: answers[q.id] ?? "",
      }));
      const result = await respondToFlow(flowId, flowAnswers);
      if (result.brief) {
        onBriefReady(result.brief);
      } else if (result.next_questions) {
        setCurrentQuestions(result.next_questions);
        setAnswers({});
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to submit answers",
      );
    } finally {
      setLoading(false);
    }
  }

  // Group questions by category
  const grouped: Record<string, FlowQuestion[]> = {};
  for (const q of currentQuestions) {
    const cat = q.category || "General";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(q);
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Answer the questions</h2>

      {Object.entries(grouped).map(([category, categoryQuestions]) => (
        <div key={category} className="space-y-4">
          <h3 className="text-lg font-medium capitalize">{category}</h3>
          {categoryQuestions.map((q) => (
            <div key={q.id} className="space-y-1">
              <label htmlFor={`q-${q.id}`} className="block font-medium">
                {q.text}
              </label>
              <textarea
                id={`q-${q.id}`}
                className="w-full border rounded p-2"
                rows={3}
                value={answers[q.id] ?? ""}
                onChange={(e) => handleAnswerChange(q.id, e.target.value)}
                disabled={loading}
              />
            </div>
          ))}
        </div>
      ))}

      {error && <p className="text-red-600">{error}</p>}

      <button
        onClick={handleSubmit}
        disabled={!allAnswered || loading}
        className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
      >
        {loading ? "Submitting..." : "Submit Answers"}
      </button>
    </div>
  );
}
