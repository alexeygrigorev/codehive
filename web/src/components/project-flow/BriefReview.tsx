import { useState } from "react";
import { finalizeFlow, type ProjectBrief } from "@/api/projectFlow";

interface BriefReviewProps {
  flowId: string;
  brief: ProjectBrief;
  onFinalized: (projectId: string) => void;
}

export default function BriefReview({
  flowId,
  brief,
  onFinalized,
}: BriefReviewProps) {
  const [name, setName] = useState(brief.name);
  const [description, setDescription] = useState(brief.description);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFinalize() {
    setLoading(true);
    setError(null);
    try {
      const result = await finalizeFlow(flowId);
      onFinalized(result.project_id);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create project",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Review Project Brief</h2>

      <div className="space-y-1">
        <label htmlFor="brief-name" className="block font-medium">
          Project Name
        </label>
        <input
          id="brief-name"
          type="text"
          className="w-full border rounded p-2"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={loading}
        />
      </div>

      <div className="space-y-1">
        <label htmlFor="brief-description" className="block font-medium">
          Description
        </label>
        <textarea
          id="brief-description"
          className="w-full border rounded p-2"
          rows={4}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={loading}
        />
      </div>

      <div className="space-y-1">
        <h3 className="font-medium">Tech Stack</h3>
        <ul className="list-disc list-inside">
          {brief.tech_stack.map((tech, i) => (
            <li key={i}>{tech}</li>
          ))}
        </ul>
      </div>

      <div className="space-y-1">
        <h3 className="font-medium">Architecture</h3>
        <p>{brief.architecture}</p>
      </div>

      {brief.open_decisions.length > 0 && (
        <div className="space-y-1">
          <h3 className="font-medium">Open Decisions</h3>
          <ul className="list-disc list-inside">
            {brief.open_decisions.map((decision, i) => (
              <li key={i}>{decision}</li>
            ))}
          </ul>
        </div>
      )}

      {brief.suggested_sessions.length > 0 && (
        <div className="space-y-1">
          <h3 className="font-medium">Suggested Sessions</h3>
          <div className="space-y-2">
            {brief.suggested_sessions.map((session, i) => (
              <div key={i} className="border rounded p-3">
                <p className="font-medium">{session.name}</p>
                <p className="text-sm text-gray-600">{session.mission}</p>
                <p className="text-xs text-gray-500">Mode: {session.mode}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {error && <p className="text-red-600">{error}</p>}

      <button
        onClick={handleFinalize}
        disabled={loading}
        className="bg-green-600 text-white px-4 py-2 rounded disabled:opacity-50"
      >
        {loading ? "Creating..." : "Create Project"}
      </button>
    </div>
  );
}
