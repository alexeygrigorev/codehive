import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchProject, type ProjectRead } from "@/api/projects";
import { createSession, fetchSessions, type SessionRead } from "@/api/sessions";
import {
  fetchIssues,
  createIssue,
  type IssueRead,
  type IssueStatus,
} from "@/api/issues";
import SessionList from "@/components/SessionList";
import IssueList from "@/components/IssueList";
import Breadcrumb from "@/components/Breadcrumb";

type Tab = "sessions" | "issues";

const engines = ["native", "claude_code"] as const;
const modes = [
  "execution",
  "brainstorm",
  "interview",
  "planning",
  "review",
] as const;

export default function ProjectPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<ProjectRead | null>(null);
  const [sessions, setSessions] = useState<SessionRead[]>([]);
  const [issues, setIssues] = useState<IssueRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("sessions");

  // Session creation form state
  const [showSessionForm, setShowSessionForm] = useState(false);
  const [sessionName, setSessionName] = useState("");
  const [sessionEngine, setSessionEngine] = useState<string>("native");
  const [sessionMode, setSessionMode] = useState<string>("execution");
  const [sessionIssueId, setSessionIssueId] = useState<string>("");
  const [creatingSession, setCreatingSession] = useState(false);

  // Issues filter state
  const [issueFilter, setIssueFilter] = useState<IssueStatus | null>(null);
  const [issuesLoaded, setIssuesLoaded] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;

    async function load() {
      try {
        const [proj, sess] = await Promise.all([
          fetchProject(projectId!),
          fetchSessions(projectId!),
        ]);
        if (cancelled) return;
        setProject(proj);
        setSessions(sess);
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof Error ? err.message : "Failed to load project",
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  // Load issues when switching to issues tab
  const loadIssues = useCallback(
    async (status?: IssueStatus | null) => {
      if (!projectId) return;
      try {
        const result = await fetchIssues(
          projectId,
          status ?? undefined,
        );
        setIssues(result);
        setIssuesLoaded(true);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load issues",
        );
      }
    },
    [projectId],
  );

  useEffect(() => {
    if (activeTab === "issues" && !issuesLoaded) {
      loadIssues(issueFilter);
    }
  }, [activeTab, issuesLoaded, issueFilter, loadIssues]);

  function handleFilterChange(status: IssueStatus | null) {
    setIssueFilter(status);
    loadIssues(status);
  }

  async function handleCreateSession(e: React.FormEvent) {
    e.preventDefault();
    if (!sessionName.trim() || !projectId) return;
    setCreatingSession(true);
    try {
      const session = await createSession(projectId, {
        name: sessionName.trim(),
        engine: sessionEngine,
        mode: sessionMode,
        ...(sessionIssueId ? { issue_id: sessionIssueId } : {}),
      });
      setSessions((prev) => [...prev, session]);
      setSessionName("");
      setSessionEngine("native");
      setSessionMode("execution");
      setSessionIssueId("");
      setShowSessionForm(false);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create session",
      );
    } finally {
      setCreatingSession(false);
    }
  }

  async function handleCreateIssue(title: string, description?: string) {
    if (!projectId) return;
    const issue = await createIssue(projectId, { title, description });
    setIssues((prev) => [...prev, issue]);
  }

  if (loading) {
    return (
      <div>
        <h1 className="text-2xl font-bold dark:text-gray-100">Project</h1>
        <p className="text-gray-500 mt-4">Loading project...</p>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div>
        <h1 className="text-2xl font-bold dark:text-gray-100">Project</h1>
        <p className="text-red-600 mt-4">
          {error ?? "Project not found"}
        </p>
        <Link
          to="/"
          className="text-blue-600 hover:underline mt-2 inline-block"
        >
          Back to Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div>
      <Breadcrumb
        segments={[
          { label: "Dashboard", to: "/" },
          { label: project.name, to: `/projects/${project.id}` },
        ]}
      />
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold dark:text-gray-100">{project.name}</h1>
          {project.archetype && (
            <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
              {project.archetype}
            </span>
          )}
        </div>
        {project.description && (
          <p className="mt-1 text-gray-600 dark:text-gray-400">{project.description}</p>
        )}
        {project.path && (
          <p className="mt-1 text-sm text-gray-500">Path: {project.path}</p>
        )}
      </div>

      {/* Tabs */}
      <div className="mt-6 border-b border-gray-200 dark:border-gray-700">
        <nav className="flex gap-4" role="tablist">
          <button
            role="tab"
            aria-selected={activeTab === "sessions"}
            onClick={() => setActiveTab("sessions")}
            className={`pb-2 text-sm font-medium border-b-2 ${
              activeTab === "sessions"
                ? "border-blue-600 text-blue-600 dark:text-blue-400"
                : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
            }`}
          >
            Sessions
          </button>
          <button
            role="tab"
            aria-selected={activeTab === "issues"}
            onClick={() => setActiveTab("issues")}
            className={`pb-2 text-sm font-medium border-b-2 ${
              activeTab === "issues"
                ? "border-blue-600 text-blue-600 dark:text-blue-400"
                : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
            }`}
          >
            Issues
          </button>
        </nav>
      </div>

      {/* Tab content */}
      <div className="mt-4">
        {activeTab === "sessions" && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold">Sessions</h2>
              <button
                onClick={() => setShowSessionForm(!showSessionForm)}
                className="bg-blue-600 text-white px-3 py-1.5 rounded text-sm"
              >
                + New Session
              </button>
            </div>

            {showSessionForm && (
              <form
                onSubmit={handleCreateSession}
                className="mb-4 p-4 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800"
              >
                <div className="mb-3">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Name
                  </label>
                  <input
                    type="text"
                    value={sessionName}
                    onChange={(e) => setSessionName(e.target.value)}
                    placeholder="Session name"
                    required
                    className="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-1.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <label htmlFor="session-engine" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Engine
                    </label>
                    <select
                      id="session-engine"
                      value={sessionEngine}
                      onChange={(e) => setSessionEngine(e.target.value)}
                      className="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-1.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    >
                      {engines.map((eng) => (
                        <option key={eng} value={eng}>
                          {eng}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="session-mode" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Mode
                    </label>
                    <select
                      id="session-mode"
                      value={sessionMode}
                      onChange={(e) => setSessionMode(e.target.value)}
                      className="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-1.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    >
                      {modes.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                {issues.length > 0 && (
                  <div className="mb-3">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Link to Issue (optional)
                    </label>
                    <select
                      value={sessionIssueId}
                      onChange={(e) => setSessionIssueId(e.target.value)}
                      className="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-1.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    >
                      <option value="">None</option>
                      {issues.map((issue) => (
                        <option key={issue.id} value={issue.id}>
                          {issue.title}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={creatingSession || !sessionName.trim()}
                    className="bg-blue-600 text-white px-3 py-1.5 rounded text-sm disabled:opacity-50"
                  >
                    {creatingSession ? "Creating..." : "Create Session"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowSessionForm(false)}
                    className="bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-3 py-1.5 rounded text-sm"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}

            <SessionList sessions={sessions} />
          </div>
        )}

        {activeTab === "issues" && (
          <IssueList
            issues={issues}
            statusFilter={issueFilter}
            onFilterChange={handleFilterChange}
            onCreateIssue={handleCreateIssue}
          />
        )}
      </div>
    </div>
  );
}
