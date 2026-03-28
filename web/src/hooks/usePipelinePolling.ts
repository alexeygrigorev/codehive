import { useEffect, useRef, useState, useCallback } from "react";
import { fetchProjects, type ProjectRead } from "@/api/projects";
import { fetchSessions } from "@/api/sessions";
import { fetchIssues } from "@/api/issues";
import {
  fetchSessionTasks,
  fetchOrchestratorStatus,
  type PipelineTask,
  type OrchestratorStatus,
} from "@/api/pipeline";

export type PipelineStatus =
  | "backlog"
  | "grooming"
  | "groomed"
  | "implementing"
  | "testing"
  | "accepting"
  | "done";

export const PIPELINE_COLUMNS: {
  status: PipelineStatus;
  label: string;
}[] = [
  { status: "backlog", label: "Backlog" },
  { status: "grooming", label: "Grooming" },
  { status: "groomed", label: "Ready" },
  { status: "implementing", label: "Implementing" },
  { status: "testing", label: "Testing" },
  { status: "accepting", label: "Accepting" },
  { status: "done", label: "Done" },
];

export interface GroupedTasks {
  [key: string]: PipelineTask[];
}

export interface UsePipelinePollingResult {
  projects: ProjectRead[];
  selectedProjectId: string | null;
  setSelectedProjectId: (id: string | null) => void;
  groupedTasks: GroupedTasks;
  orchestratorStatus: OrchestratorStatus | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

const POLL_INTERVAL = 10_000;

export function usePipelinePolling(): UsePipelinePollingResult {
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    null,
  );
  const [groupedTasks, setGroupedTasks] = useState<GroupedTasks>({});
  const [orchestratorStatus, setOrchestratorStatus] =
    useState<OrchestratorStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [projectsLoaded, setProjectsLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load projects on mount
  useEffect(() => {
    let cancelled = false;
    async function loadProjects() {
      try {
        const data = await fetchProjects();
        if (cancelled) return;
        setProjects(data);
        setProjectsLoaded(true);
        if (data.length > 0 && !selectedProjectId) {
          setSelectedProjectId(data[0].id);
        }
      } catch (err) {
        if (cancelled) return;
        setProjectsLoaded(true);
        setError(
          err instanceof Error ? err.message : "Failed to load projects",
        );
      }
    }
    loadProjects();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchPipelineData = useCallback(async () => {
    if (!selectedProjectId) {
      // Only stop loading if projects have been loaded (no project selected means empty list)
      if (projectsLoaded) setLoading(false);
      return;
    }

    try {
      // Fetch issues for the project to find sessions
      const issues = await fetchIssues(selectedProjectId);
      const sessions = await fetchSessions(selectedProjectId);

      // Gather all tasks from all sessions
      const allTasks: PipelineTask[] = [];
      await Promise.all(
        sessions.map(async (session) => {
          try {
            const tasks = await fetchSessionTasks(session.id);
            allTasks.push(...tasks);
          } catch {
            // Session may have no tasks
          }
        }),
      );

      // Also check for issues without sessions (to avoid missing tasks)
      // The tasks are already fetched from sessions

      // Group by pipeline_status
      const grouped: GroupedTasks = {};
      for (const col of PIPELINE_COLUMNS) {
        grouped[col.status] = [];
      }
      for (const task of allTasks) {
        const status = task.pipeline_status || "backlog";
        if (grouped[status]) {
          grouped[status].push(task);
        } else {
          grouped["backlog"].push(task);
        }
      }

      setGroupedTasks(grouped);

      // Fetch orchestrator status
      try {
        const orchStatus =
          await fetchOrchestratorStatus(selectedProjectId);
        setOrchestratorStatus(orchStatus);
      } catch {
        setOrchestratorStatus({
          status: "stopped",
          project_id: selectedProjectId,
          current_batch: null,
          active_sessions: null,
          flagged_tasks: null,
        });
      }

      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load pipeline data",
      );
    } finally {
      setLoading(false);
    }
    // We intentionally suppress the lint warning about issues not being used -
    // fetchIssues is called to verify project exists and could be used for enrichment
  }, [selectedProjectId, projectsLoaded]);

  // Poll on interval
  useEffect(() => {
    fetchPipelineData();

    intervalRef.current = setInterval(fetchPipelineData, POLL_INTERVAL);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchPipelineData]);

  const refresh = useCallback(() => {
    fetchPipelineData();
  }, [fetchPipelineData]);

  return {
    projects,
    selectedProjectId,
    setSelectedProjectId,
    groupedTasks,
    orchestratorStatus,
    loading,
    error,
    refresh,
  };
}
