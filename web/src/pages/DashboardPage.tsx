import { useEffect, useState } from "react";
import { fetchProjects, type ProjectRead } from "@/api/projects";
import { fetchSessions } from "@/api/sessions";
import ProjectCard from "@/components/ProjectCard";

export default function DashboardPage() {
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [sessionCounts, setSessionCounts] = useState<Record<string, number>>(
    {},
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await fetchProjects();
        if (cancelled) return;
        setProjects(data);

        const counts: Record<string, number> = {};
        await Promise.all(
          data.map(async (p) => {
            try {
              const sessions = await fetchSessions(p.id);
              counts[p.id] = sessions.length;
            } catch {
              counts[p.id] = 0;
            }
          }),
        );
        if (cancelled) return;
        setSessionCounts(counts);
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof Error ? err.message : "Failed to load projects",
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-gray-500 mt-4">Loading projects...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-red-600 mt-4">{error}</p>
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-gray-500 mt-4">
          No projects yet. Create your first project to get started.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((project) => (
          <ProjectCard
            key={project.id}
            id={project.id}
            name={project.name}
            description={project.description}
            archetype={project.archetype}
            sessionCount={sessionCounts[project.id] ?? 0}
          />
        ))}
      </div>
    </div>
  );
}
