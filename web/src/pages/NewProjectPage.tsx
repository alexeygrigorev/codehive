import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  startFlow,
  type FlowStartResult,
  type ProjectBrief,
} from "@/api/projectFlow";
import { createProject } from "@/api/projects";
import FlowChat from "@/components/project-flow/FlowChat";
import BriefReview from "@/components/project-flow/BriefReview";

type Step = "select" | "chat" | "review";

const FLOW_TYPES = [
  {
    type: "brainstorm",
    title: "Brainstorm",
    description:
      "Free-form ideation. Explore ideas, identify gaps, and shape your project vision.",
    requiresInput: false,
  },
  {
    type: "interview",
    title: "Guided Interview",
    description:
      "Structured requirements gathering through batched questions to build a complete project spec.",
    requiresInput: false,
  },
  {
    type: "spec_from_notes",
    title: "From Notes",
    description:
      "Paste your existing notes, docs, or ideas and let the system structure them into a project.",
    requiresInput: true,
  },
  {
    type: "start_from_repo",
    title: "From Repository",
    description:
      "Start from an existing repository URL to analyze and build a project around it.",
    requiresInput: true,
  },
];

export default function NewProjectPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("select");
  const [flowResult, setFlowResult] = useState<FlowStartResult | null>(null);
  const [brief, setBrief] = useState<ProjectBrief | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initialInput, setInitialInput] = useState("");
  const [selectedType, setSelectedType] = useState<string | null>(null);

  async function handleCreateEmpty() {
    const name = prompt("Project name:");
    if (!name?.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const project = await createProject({
        name: name.trim(),
      });
      navigate(`/projects/${project.id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create project",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectFlow(flowType: string, requiresInput: boolean) {
    if (requiresInput && !initialInput.trim()) {
      setSelectedType(flowType);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const result = await startFlow({
        flow_type: flowType,
        initial_input: initialInput.trim() || undefined,
      });
      setFlowResult(result);
      setStep("chat");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start flow");
    } finally {
      setLoading(false);
    }
  }

  function handleBriefReady(b: ProjectBrief) {
    setBrief(b);
    setStep("review");
  }

  function handleFinalized(projectId: string) {
    navigate(`/projects/${projectId}`);
  }

  if (step === "chat" && flowResult) {
    return (
      <div className="max-w-2xl mx-auto p-4">
        <FlowChat
          flowId={flowResult.flow_id}
          questions={flowResult.first_questions}
          onBriefReady={handleBriefReady}
        />
      </div>
    );
  }

  if (step === "review" && flowResult && brief) {
    return (
      <div className="max-w-2xl mx-auto p-4">
        <BriefReview
          flowId={flowResult.flow_id}
          brief={brief}
          onFinalized={handleFinalized}
        />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-4">
      <h1 className="text-2xl font-bold dark:text-gray-100 mb-6">New Project</h1>

      <button
        onClick={handleCreateEmpty}
        disabled={loading}
        className="w-full border-2 border-dashed dark:border-gray-600 rounded-lg p-4 text-left hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors disabled:opacity-50 mb-4"
      >
        <h3 className="font-semibold text-lg">Empty Project</h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
          Create a blank project and start chatting right away.
        </p>
      </button>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {FLOW_TYPES.map((flow) => (
          <button
            key={flow.type}
            onClick={() => handleSelectFlow(flow.type, flow.requiresInput)}
            disabled={loading}
            className="border dark:border-gray-600 rounded-lg p-4 text-left hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors disabled:opacity-50"
          >
            <h3 className="font-semibold text-lg">{flow.title}</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{flow.description}</p>
          </button>
        ))}
      </div>

      {(selectedType === "spec_from_notes" || selectedType === "start_from_repo") && (
        <div className="mt-4 space-y-2">
          <label htmlFor="initial-input" className="block font-medium">
            {selectedType === "spec_from_notes"
              ? "Paste your notes"
              : "Repository URL"}
          </label>
          <textarea
            id="initial-input"
            className="w-full border dark:border-gray-600 rounded p-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            rows={4}
            value={initialInput}
            onChange={(e) => setInitialInput(e.target.value)}
            placeholder={
              selectedType === "spec_from_notes"
                ? "Paste your notes, ideas, or documentation here..."
                : "https://github.com/user/repo"
            }
          />
          <button
            onClick={() => handleSelectFlow(selectedType, true)}
            disabled={loading || !initialInput.trim()}
            className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
          >
            {loading ? "Starting..." : "Continue"}
          </button>
        </div>
      )}

      {loading && !selectedType && (
        <p className="text-gray-500 mt-4">Starting flow...</p>
      )}
      {error && <p className="text-red-600 mt-4">{error}</p>}
    </div>
  );
}
