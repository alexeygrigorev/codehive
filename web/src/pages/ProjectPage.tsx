import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchProject, type ProjectRead } from "@/api/projects";
import { createSession, fetchSessions, type SessionRead } from "@/api/sessions";
import SessionList from "@/components/SessionList";

export default function ProjectPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<ProjectRead | null>(null);
  const [sessions, setSessions] = useState<SessionRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

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

  if (loading) {
    return (
      <div>
        <h1 className="text-2xl font-bold">Project</h1>
        <p className="text-gray-500 mt-4">Loading project...</p>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div>
        <h1 className="text-2xl font-bold">Project</h1>
        <p className="text-red-600 mt-4">
          {error ?? "Project not found"}
        </p>
        <Link to="/" className="text-blue-600 hover:underline mt-2 inline-block">
          Back to Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div>
      <Link to="/" className="text-sm text-blue-600 hover:underline">
        &larr; Back to Dashboard
      </Link>
      <div className="mt-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">{project.name}</h1>
          {project.archetype && (
            <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
              {project.archetype}
            </span>
          )}
        </div>
        {project.description && (
          <p className="mt-1 text-gray-600">{project.description}</p>
        )}
        {project.path && (
          <p className="mt-1 text-sm text-gray-500">Path: {project.path}</p>
        )}
      </div>
      <div className="mt-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Sessions</h2>
          <button
            onClick={async () => {
              const name = prompt("Session name:", "New Session");
              if (!name?.trim()) return;
              setCreating(true);
              try {
                const session = await createSession(projectId!, { name: name.trim() });
                setSessions((prev) => [...prev, session]);
              } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to create session");
              } finally {
                setCreating(false);
              }
            }}
            disabled={creating}
            className="bg-blue-600 text-white px-3 py-1.5 rounded text-sm disabled:opacity-50"
          >
            {creating ? "Creating..." : "+ New Session"}
          </button>
        </div>
        <SessionList sessions={sessions} />
      </div>
    </div>
  );
}
