import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  startFlow,
  type FlowStartResult,
  type ProjectBrief,
} from "@/api/projectFlow";
import { createProject } from "@/api/projects";
import {
  fetchDefaultDirectory,
  fetchDirectories,
  type DirectoryEntry,
} from "@/api/system";
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
    comingSoon: true,
  },
  {
    type: "interview",
    title: "Guided Interview",
    description:
      "Structured requirements gathering through batched questions to build a complete project spec.",
    requiresInput: false,
    comingSoon: true,
  },
  {
    type: "spec_from_notes",
    title: "From Notes",
    description:
      "Paste your existing notes, docs, or ideas and let the system structure them into a project.",
    requiresInput: true,
    comingSoon: true,
  },
  {
    type: "start_from_repo",
    title: "From Repository",
    description:
      "Start from an existing repository URL to analyze and build a project around it.",
    requiresInput: true,
    comingSoon: true,
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
  const [showEmptyForm, setShowEmptyForm] = useState(false);
  const [directoryPath, setDirectoryPath] = useState("");
  const [projectName, setProjectName] = useState("");
  const [pathError, setPathError] = useState<string | null>(null);
  const [userEditedName, setUserEditedName] = useState(false);
  const [gitInit, setGitInit] = useState(true);
  const [gitInitAutoDisabled, setGitInitAutoDisabled] = useState(false);
  const [browseOpen, setBrowseOpen] = useState(true);
  const [browseEntries, setBrowseEntries] = useState<DirectoryEntry[]>([]);
  const [browseParent, setBrowseParent] = useState<string | null>(null);
  const [browseError, setBrowseError] = useState<string | null>(null);
  const [browseLoading, setBrowseLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch default directory when form opens
  useEffect(() => {
    if (showEmptyForm && !directoryPath) {
      fetchDefaultDirectory()
        .then((res) => {
          setDirectoryPath(res.default_directory);
        })
        .catch(() => {
          // Silently ignore -- user can type manually
        });
    }
  }, [showEmptyForm]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-derive project name from path
  useEffect(() => {
    if (!userEditedName && directoryPath.trim()) {
      const parts = directoryPath.replace(/\/+$/, "").split("/");
      const basename = parts[parts.length - 1] || "";
      setProjectName(basename);
    }
  }, [directoryPath, userEditedName]);

  // Debounced directory browsing
  const loadDirectories = useCallback((path: string) => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }
    debounceRef.current = setTimeout(async () => {
      const trimmed = path.trim();
      if (!trimmed || !trimmed.startsWith("/")) {
        setBrowseEntries([]);
        setBrowseParent(null);
        setBrowseError(null);
        return;
      }
      setBrowseLoading(true);
      setBrowseError(null);
      try {
        const res = await fetchDirectories(trimmed);
        setBrowseEntries(res.directories);
        setBrowseParent(res.parent);
        setBrowseError(null);
      } catch (err) {
        setBrowseEntries([]);
        setBrowseParent(null);
        setBrowseError(
          err instanceof Error ? err.message : "Failed to load directories",
        );
      } finally {
        setBrowseLoading(false);
      }
    }, 300);
  }, []);

  useEffect(() => {
    if (showEmptyForm && browseOpen && directoryPath.trim()) {
      loadDirectories(directoryPath);
    }
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [directoryPath, showEmptyForm, browseOpen, loadDirectories]);

  function handleSelectDirectory(entry: DirectoryEntry) {
    setDirectoryPath(entry.path);
    if (entry.has_git) {
      setGitInit(false);
      setGitInitAutoDisabled(true);
    } else {
      setGitInitAutoDisabled(false);
      setGitInit(true);
    }
  }

  function handleNavigateParent() {
    if (browseParent) {
      setDirectoryPath(browseParent);
    }
  }

  async function handleCreateEmpty() {
    setPathError(null);
    const trimmedPath = directoryPath.trim();
    if (!trimmedPath) {
      setPathError("Directory path is required");
      return;
    }
    if (!trimmedPath.startsWith("/")) {
      setPathError("Path must be absolute (start with /)");
      return;
    }
    const name =
      projectName.trim() ||
      trimmedPath
        .replace(/\/+$/, "")
        .split("/")
        .pop() ||
      "project";

    setLoading(true);
    setError(null);
    try {
      const project = await createProject({
        name,
        path: trimmedPath,
        git_init: gitInit,
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
      <h1 className="text-2xl font-bold dark:text-gray-100 mb-6">
        New Project
      </h1>

      <button
        onClick={() => setShowEmptyForm(!showEmptyForm)}
        disabled={loading}
        className="w-full border-2 border-dashed dark:border-gray-600 rounded-lg p-4 text-left hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors disabled:opacity-50 mb-4"
      >
        <h3 className="font-semibold text-lg dark:text-gray-100">
          Empty Project
        </h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
          Create a blank project and start chatting right away.
        </p>
      </button>

      {showEmptyForm && (
        <div className="mt-4 space-y-3 border dark:border-gray-600 rounded-lg p-4 mb-4">
          <div>
            <label
              htmlFor="dir-path"
              className="block font-medium dark:text-gray-200 mb-1"
            >
              Directory Path
            </label>
            <input
              id="dir-path"
              type="text"
              className="w-full border dark:border-gray-600 rounded p-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              placeholder="/home/user/projects/myapp"
              value={directoryPath}
              onChange={(e) => {
                setDirectoryPath(e.target.value);
                if (gitInitAutoDisabled) {
                  setGitInitAutoDisabled(false);
                  setGitInit(true);
                }
              }}
            />
            {pathError && (
              <p className="text-red-600 text-sm mt-1">{pathError}</p>
            )}
          </div>

          {/* Directory browser panel */}
          <div>
            <button
              type="button"
              onClick={() => setBrowseOpen(!browseOpen)}
              className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
              data-testid="browse-toggle"
            >
              {browseOpen ? "Hide Browser" : "Browse"}
            </button>
            {browseOpen && (
              <div
                className="mt-2 border dark:border-gray-600 rounded max-h-48 overflow-y-auto bg-white dark:bg-gray-800"
                data-testid="browse-panel"
              >
                {browseLoading && (
                  <p className="text-sm text-gray-500 dark:text-gray-400 p-2">
                    Loading...
                  </p>
                )}
                {browseError && (
                  <p className="text-sm text-red-500 dark:text-red-400 p-2">
                    {browseError}
                  </p>
                )}
                {!browseLoading && !browseError && (
                  <ul className="divide-y dark:divide-gray-700">
                    {browseParent && (
                      <li>
                        <button
                          type="button"
                          onClick={handleNavigateParent}
                          className="w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 text-sm dark:text-gray-200"
                          data-testid="browse-parent"
                        >
                          ..
                        </button>
                      </li>
                    )}
                    {browseEntries.map((entry) => (
                      <li key={entry.path}>
                        <button
                          type="button"
                          onClick={() => handleSelectDirectory(entry)}
                          className="w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 text-sm dark:text-gray-200 flex items-center gap-2"
                          data-testid={`browse-entry-${entry.name}`}
                        >
                          <span className="text-gray-400">&#128193;</span>
                          <span>{entry.name}</span>
                          {entry.has_git && (
                            <span className="ml-auto text-xs font-medium px-1.5 py-0.5 rounded bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
                              git
                            </span>
                          )}
                        </button>
                      </li>
                    ))}
                    {browseEntries.length === 0 && !browseParent && (
                      <li className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
                        No subdirectories
                      </li>
                    )}
                  </ul>
                )}
              </div>
            )}
          </div>

          <div>
            <label
              htmlFor="proj-name"
              className="block font-medium dark:text-gray-200 mb-1"
            >
              Project Name{" "}
              <span className="text-sm text-gray-500 dark:text-gray-400">
                (optional)
              </span>
            </label>
            <input
              id="proj-name"
              type="text"
              className="w-full border dark:border-gray-600 rounded p-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              placeholder="Auto-derived from directory name"
              value={projectName}
              onChange={(e) => {
                setProjectName(e.target.value);
                setUserEditedName(true);
              }}
            />
          </div>

          {/* Git init checkbox */}
          <div className="flex items-center gap-2">
            <input
              id="git-init"
              type="checkbox"
              checked={gitInit}
              onChange={(e) => {
                setGitInit(e.target.checked);
                setGitInitAutoDisabled(false);
              }}
              className="rounded border-gray-300 dark:border-gray-600"
              data-testid="git-init-checkbox"
            />
            <label
              htmlFor="git-init"
              className="text-sm dark:text-gray-200"
            >
              Initialize git repository
            </label>
            {gitInitAutoDisabled && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                (already a git repo)
              </span>
            )}
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleCreateEmpty}
              disabled={loading}
              className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
            >
              {loading ? "Creating..." : "Create Project"}
            </button>
            <button
              onClick={() => {
                setShowEmptyForm(false);
                setDirectoryPath("");
                setProjectName("");
                setPathError(null);
                setUserEditedName(false);
                setGitInit(true);
                setGitInitAutoDisabled(false);
              }}
              className="px-4 py-2 rounded border dark:border-gray-600 text-gray-700 dark:text-gray-300"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {FLOW_TYPES.map((flow) => (
          <div
            key={flow.type}
            data-testid={`flow-card-${flow.type}`}
            className={
              flow.comingSoon
                ? "border dark:border-gray-600 rounded-lg p-4 text-left opacity-50 cursor-not-allowed"
                : "border dark:border-gray-600 rounded-lg p-4 text-left hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors cursor-pointer"
            }
            role={flow.comingSoon ? undefined : "button"}
            tabIndex={flow.comingSoon ? undefined : 0}
            onClick={
              flow.comingSoon
                ? undefined
                : () => handleSelectFlow(flow.type, flow.requiresInput)
            }
            onKeyDown={
              flow.comingSoon
                ? undefined
                : (e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      handleSelectFlow(flow.type, flow.requiresInput);
                    }
                  }
            }
            aria-disabled={flow.comingSoon ? true : undefined}
          >
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-lg dark:text-gray-100">
                {flow.title}
              </h3>
              {flow.comingSoon && (
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                  Coming soon
                </span>
              )}
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              {flow.description}
            </p>
          </div>
        ))}
      </div>

      {(selectedType === "spec_from_notes" ||
        selectedType === "start_from_repo") && (
        <div className="mt-4 space-y-2">
          <label
            htmlFor="initial-input"
            className="block font-medium dark:text-gray-200"
          >
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
        <p className="text-gray-500 dark:text-gray-400 mt-4">
          Starting flow...
        </p>
      )}
      {error && <p className="text-red-600 mt-4">{error}</p>}
    </div>
  );
}
