import { useEffect, useState, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { fetchProject, type ProjectRead } from "@/api/projects";
import { createSession, fetchSessions, type SessionRead } from "@/api/sessions";
import {
  fetchIssues,
  createIssue,
  type IssueRead,
  type IssueStatus,
} from "@/api/issues";
import { fetchTeam, type AgentProfileRead } from "@/api/team";
import SessionList from "@/components/SessionList";
import IssueList from "@/components/IssueList";
import Breadcrumb from "@/components/Breadcrumb";
import NewSessionDialog from "@/components/NewSessionDialog";

type Tab = "sessions" | "issues" | "team";

export default function ProjectPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<ProjectRead | null>(null);
  const [sessions, setSessions] = useState<SessionRead[]>([]);
  const [issues, setIssues] = useState<IssueRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("sessions");
  const [creatingSession, setCreatingSession] = useState(false);
  const [showNewSessionDialog, setShowNewSessionDialog] = useState(false);

  const [team, setTeam] = useState<AgentProfileRead[]>([]);
  const [teamLoaded, setTeamLoaded] = useState(false);

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

  useEffect(() => {
    if (activeTab === "team" && !teamLoaded && projectId) {
      fetchTeam(projectId)
        .then((t) => {
          setTeam(t);
          setTeamLoaded(true);
        })
        .catch((err) =>
          setError(err instanceof Error ? err.message : "Failed to load team"),
        );
    }
  }, [activeTab, teamLoaded, projectId]);

  function handleFilterChange(status: IssueStatus | null) {
    setIssueFilter(status);
    loadIssues(status);
  }

  async function handleNewSession(data: {
    name: string;
    provider: string;
    model: string;
  }) {
    if (!projectId) return;
    setCreatingSession(true);
    try {
      const session = await createSession(projectId, {
        name: data.name,
        engine: "claude_code",
        mode: "execution",
        config: { provider: data.provider, model: data.model },
      });
      setShowNewSessionDialog(false);
      navigate(`/sessions/${session.id}`);
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
        <p className="text-gray-500 dark:text-gray-400 mt-4">Loading project...</p>
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
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Path: {project.path}</p>
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
          <button
            role="tab"
            aria-selected={activeTab === "team"}
            onClick={() => setActiveTab("team")}
            className={`pb-2 text-sm font-medium border-b-2 ${
              activeTab === "team"
                ? "border-blue-600 text-blue-600 dark:text-blue-400"
                : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
            }`}
          >
            Team
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
                onClick={() => setShowNewSessionDialog(true)}
                disabled={creatingSession}
                className="bg-blue-600 text-white px-3 py-1.5 rounded text-sm disabled:opacity-50"
              >
                + New Session
              </button>
            </div>

            <SessionList sessions={sessions} />
            <NewSessionDialog
              open={showNewSessionDialog}
              onClose={() => setShowNewSessionDialog(false)}
              onSubmit={handleNewSession}
              creating={creatingSession}
            />
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

        {activeTab === "team" && (
          <div>
            <h2 className="text-lg font-semibold mb-3">Team</h2>
            {team.length === 0 ? (
              <p className="text-gray-500 dark:text-gray-400 text-sm">No team members.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {team.map((agent) => (
                  <div
                    key={agent.id}
                    data-testid="team-member-card"
                    className="flex items-center gap-3 p-3 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800"
                  >
                    <img
                      src={agent.avatar_url}
                      alt={agent.name}
                      className="w-8 h-8 rounded-full"
                      data-testid="team-member-avatar"
                    />
                    <div>
                      <p className="font-medium text-gray-900 dark:text-gray-100">
                        {agent.name}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {agent.role.toUpperCase()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
