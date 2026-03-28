import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  fetchArchivedProjects,
  unarchiveProject,
  deleteProject,
  type ProjectRead,
} from "@/api/projects";
import Breadcrumb from "@/components/Breadcrumb";
import ConfirmDialog from "@/components/ConfirmDialog";

export default function ArchivedProjectsPage() {
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Dialog state
  const [restoreTarget, setRestoreTarget] = useState<ProjectRead | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProjectRead | null>(null);

  const loadProjects = useCallback(async () => {
    try {
      const data = await fetchArchivedProjects();
      setProjects(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load archived projects",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  async function handleRestore() {
    if (!restoreTarget) return;
    try {
      await unarchiveProject(restoreTarget.id);
      setProjects((prev) => prev.filter((p) => p.id !== restoreTarget.id));
      setRestoreTarget(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to restore project",
      );
      setRestoreTarget(null);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteProject(deleteTarget.id);
      setProjects((prev) => prev.filter((p) => p.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to delete project",
      );
      setDeleteTarget(null);
    }
  }

  if (loading) {
    return (
      <div>
        <h1 className="text-2xl font-bold dark:text-gray-100">
          Archived Projects
        </h1>
        <p className="text-gray-500 dark:text-gray-400 mt-4">Loading...</p>
      </div>
    );
  }

  return (
    <div>
      <Breadcrumb
        segments={[
          { label: "Dashboard", to: "/" },
          { label: "Archived Projects", to: "/projects/archived" },
        ]}
      />
      <h1 className="text-2xl font-bold dark:text-gray-100">
        Archived Projects
      </h1>

      {error && <p className="text-red-600 dark:text-red-400 mt-2">{error}</p>}

      {projects.length === 0 && !error && (
        <p className="text-gray-500 dark:text-gray-400 mt-4">
          No archived projects.
        </p>
      )}

      {projects.length > 0 && (
        <div className="mt-4 space-y-3">
          {projects.map((project) => (
            <div
              key={project.id}
              className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800"
              data-testid="archived-project-card"
            >
              <div>
                <p className="font-medium text-gray-900 dark:text-gray-100">
                  {project.name}
                </p>
                {project.description && (
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                    {project.description}
                  </p>
                )}
                {project.archived_at && (
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                    Archived{" "}
                    {new Date(project.archived_at).toLocaleDateString()}
                  </p>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setRestoreTarget(project)}
                  className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                  data-testid="restore-project-btn"
                >
                  Restore
                </button>
                <button
                  onClick={() => setDeleteTarget(project)}
                  className="px-3 py-1.5 text-sm bg-red-600 text-white rounded hover:bg-red-700"
                  data-testid="delete-project-btn"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Restore confirmation */}
      <ConfirmDialog
        open={restoreTarget !== null}
        title="Restore project"
        message={`Restore '${restoreTarget?.name}'? It will reappear in your sidebar and dashboard.`}
        confirmLabel="Restore"
        onConfirm={handleRestore}
        onCancel={() => setRestoreTarget(null)}
      />

      {/* Delete confirmation (requires typing project name) */}
      <ConfirmDialog
        open={deleteTarget !== null}
        title="Permanently delete project"
        message={`Permanently delete '${deleteTarget?.name}'? This will delete the project and ALL its sessions, issues, team members, and data. This action cannot be undone.`}
        confirmLabel="Delete permanently"
        destructive
        requiredText={deleteTarget?.name}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
