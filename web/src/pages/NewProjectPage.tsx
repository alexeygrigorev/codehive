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
import {
  fetchGhStatus,
  fetchGhRepos,
  cloneRepo,
  type RepoItem,
} from "@/api/githubRepos";
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
      "Import a GitHub repository and create a project from it.",
    requiresInput: false,
    comingSoon: false,
  },
];

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const seconds = Math.floor((now - then) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

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

  // --- Repo picker state ---
  const [showRepoPicker, setShowRepoPicker] = useState(false);
  const [ghAvailable, setGhAvailable] = useState<boolean | null>(null);
  const [ghError, setGhError] = useState<string | null>(null);
  const [repos, setRepos] = useState<RepoItem[]>([]);
  const [reposLoading, setReposLoading] = useState(false);
  const [repoSearch, setRepoSearch] = useState("");
  const [repoOwner, setRepoOwner] = useState("");
  const [selectedRepo, setSelectedRepo] = useState<RepoItem | null>(null);
  const [cloneDest, setCloneDest] = useState("");
  const [cloneProjectName, setCloneProjectName] = useState("");
  const [cloneLoading, setCloneLoading] = useState(false);
  const [cloneError, setCloneError] = useState<string | null>(null);
  const [defaultDir, setDefaultDir] = useState("");
  const ownerDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  // --- Repo picker effects ---

  // Check gh status and load repos when picker opens
  useEffect(() => {
    if (!showRepoPicker) return;
    let cancelled = false;

    async function init() {
      setGhAvailable(null);
      setGhError(null);
      setRepos([]);
      setSelectedRepo(null);
      setCloneError(null);

      try {
        const status = await fetchGhStatus();
        if (cancelled) return;
        if (!status.available || !status.authenticated) {
          setGhAvailable(false);
          setGhError(
            status.error || "GitHub CLI is not available or not authenticated.",
          );
          return;
        }
        setGhAvailable(true);
      } catch {
        if (cancelled) return;
        setGhAvailable(false);
        setGhError("Failed to check GitHub CLI status.");
        return;
      }

      // Fetch default dir for clone destination
      try {
        const dirRes = await fetchDefaultDirectory();
        if (!cancelled) setDefaultDir(dirRes.default_directory);
      } catch {
        // ignore
      }

      // Fetch repos
      setReposLoading(true);
      try {
        const res = await fetchGhRepos();
        if (!cancelled) setRepos(res.repos);
      } catch {
        if (!cancelled) setGhError("Failed to load repositories.");
      } finally {
        if (!cancelled) setReposLoading(false);
      }
    }

    init();
    return () => {
      cancelled = true;
    };
  }, [showRepoPicker]);

  // Owner change triggers re-fetch with debounce
  function handleOwnerChange(value: string) {
    setRepoOwner(value);
    if (ownerDebounceRef.current) clearTimeout(ownerDebounceRef.current);
    ownerDebounceRef.current = setTimeout(async () => {
      setReposLoading(true);
      setGhError(null);
      try {
        const res = await fetchGhRepos({
          owner: value.trim() || undefined,
        });
        setRepos(res.repos);
      } catch {
        setGhError("Failed to load repositories.");
      } finally {
        setReposLoading(false);
      }
    }, 500);
  }

  // Select a repo
  function handleSelectRepo(repo: RepoItem) {
    setSelectedRepo(repo);
    setCloneProjectName(repo.name);
    const base = defaultDir.replace(/\/+$/, "");
    setCloneDest(base ? `${base}/${repo.name}` : repo.name);
    setCloneError(null);
  }

  // Clone & Create
  async function handleClone() {
    if (!selectedRepo) return;
    setCloneLoading(true);
    setCloneError(null);
    try {
      const result = await cloneRepo({
        repo_url: selectedRepo.clone_url,
        destination: cloneDest,
        project_name: cloneProjectName || selectedRepo.name,
      });
      navigate(`/projects/${result.project_id}`);
    } catch (err) {
      setCloneError(
        err instanceof Error ? err.message : "Clone failed",
      );
    } finally {
      setCloneLoading(false);
    }
  }

  // Filter repos by search term (client-side)
  const filteredRepos = repoSearch
    ? repos.filter((r) =>
        r.name.toLowerCase().includes(repoSearch.toLowerCase()),
      )
    : repos;

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
    if (flowType === "start_from_repo") {
      setShowRepoPicker(!showRepoPicker);
      setShowEmptyForm(false);
      return;
    }

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
        onClick={() => {
          setShowEmptyForm(!showEmptyForm);
          setShowRepoPicker(false);
        }}
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

      {/* Repo picker panel */}
      {showRepoPicker && (
        <div
          className="mt-4 border dark:border-gray-600 rounded-lg p-4"
          data-testid="repo-picker-panel"
        >
          {ghAvailable === null && (
            <p
              className="text-sm text-gray-500 dark:text-gray-400"
              data-testid="repo-picker-checking"
            >
              Checking GitHub access...
            </p>
          )}

          {ghAvailable === false && ghError && (
            <div
              className="text-sm text-red-600 dark:text-red-400"
              data-testid="repo-picker-error"
            >
              {ghError}
            </div>
          )}

          {ghAvailable === true && (
            <>
              {/* Search and owner fields */}
              <div className="flex gap-2 mb-3">
                <input
                  type="text"
                  placeholder="Search repos..."
                  value={repoSearch}
                  onChange={(e) => setRepoSearch(e.target.value)}
                  className="flex-1 border dark:border-gray-600 rounded p-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  data-testid="repo-search-input"
                />
                <input
                  type="text"
                  placeholder="Owner / org"
                  value={repoOwner}
                  onChange={(e) => handleOwnerChange(e.target.value)}
                  className="w-36 border dark:border-gray-600 rounded p-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  data-testid="repo-owner-input"
                />
              </div>

              {/* Repo list */}
              {reposLoading && (
                <p className="text-sm text-gray-500 dark:text-gray-400 py-2">
                  Loading repositories...
                </p>
              )}

              {!reposLoading && filteredRepos.length === 0 && (
                <p
                  className="text-sm text-gray-500 dark:text-gray-400 py-2"
                  data-testid="repo-list-empty"
                >
                  No repositories found
                </p>
              )}

              {!reposLoading && filteredRepos.length > 0 && (
                <div
                  className="border dark:border-gray-600 rounded max-h-64 overflow-y-auto bg-white dark:bg-gray-800"
                  data-testid="repo-list"
                >
                  <ul className="divide-y dark:divide-gray-700">
                    {filteredRepos.map((repo) => (
                      <li key={repo.full_name}>
                        <button
                          type="button"
                          onClick={() => handleSelectRepo(repo)}
                          className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                            selectedRepo?.full_name === repo.full_name
                              ? "bg-blue-50 dark:bg-blue-900/40 border-l-2 border-blue-500"
                              : "hover:bg-gray-50 dark:hover:bg-gray-700"
                          }`}
                          data-testid={`repo-row-${repo.name}`}
                        >
                          <div className="flex items-center gap-2">
                            <span className="font-medium dark:text-gray-100">
                              {repo.name}
                            </span>
                            {repo.language && (
                              <span
                                className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"
                                data-testid={`repo-lang-${repo.name}`}
                              >
                                {repo.language}
                              </span>
                            )}
                            <span
                              className={`text-xs px-1.5 py-0.5 rounded ${
                                repo.is_private
                                  ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300"
                                  : "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                              }`}
                              data-testid={`repo-visibility-${repo.name}`}
                            >
                              {repo.is_private ? "private" : "public"}
                            </span>
                            {repo.updated_at && (
                              <span className="ml-auto text-xs text-gray-400 dark:text-gray-500">
                                {timeAgo(repo.updated_at)}
                              </span>
                            )}
                          </div>
                          {repo.description && (
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate">
                              {repo.description}
                            </p>
                          )}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Clone form - shown when a repo is selected */}
              {selectedRepo && (
                <div
                  className="mt-3 space-y-2 border-t dark:border-gray-600 pt-3"
                  data-testid="clone-form"
                >
                  <div>
                    <label
                      htmlFor="clone-dest"
                      className="block text-sm font-medium dark:text-gray-200 mb-1"
                    >
                      Clone to:
                    </label>
                    <input
                      id="clone-dest"
                      type="text"
                      value={cloneDest}
                      onChange={(e) => setCloneDest(e.target.value)}
                      className="w-full border dark:border-gray-600 rounded p-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                      data-testid="clone-dest-input"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="clone-name"
                      className="block text-sm font-medium dark:text-gray-200 mb-1"
                    >
                      Project Name:
                    </label>
                    <input
                      id="clone-name"
                      type="text"
                      value={cloneProjectName}
                      onChange={(e) => setCloneProjectName(e.target.value)}
                      className="w-full border dark:border-gray-600 rounded p-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                      data-testid="clone-name-input"
                    />
                  </div>
                  <button
                    onClick={handleClone}
                    disabled={cloneLoading || !cloneDest.trim()}
                    className="bg-blue-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
                    data-testid="clone-button"
                  >
                    {cloneLoading
                      ? "Cloning repository..."
                      : "Clone & Create Project"}
                  </button>
                  {cloneError && (
                    <p
                      className="text-sm text-red-600 dark:text-red-400 mt-1"
                      data-testid="clone-error"
                    >
                      {cloneError}
                    </p>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {selectedType === "spec_from_notes" && (
        <div className="mt-4 space-y-2">
          <label
            htmlFor="initial-input"
            className="block font-medium dark:text-gray-200"
          >
            Paste your notes
          </label>
          <textarea
            id="initial-input"
            className="w-full border dark:border-gray-600 rounded p-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            rows={4}
            value={initialInput}
            onChange={(e) => setInitialInput(e.target.value)}
            placeholder="Paste your notes, ideas, or documentation here..."
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
