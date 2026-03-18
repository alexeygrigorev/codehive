import { useEffect, useState, useCallback } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { fetchProjects, type ProjectRead } from "@/api/projects";
import { fetchSessions, type SessionRead } from "@/api/sessions";
import UserMenu from "@/components/UserMenu";

const SIDEBAR_COLLAPSED_KEY = "codehive-sidebar-collapsed";

const statusDotColors: Record<string, string> = {
  idle: "bg-gray-400",
  planning: "bg-yellow-400",
  executing: "bg-blue-400",
  waiting_input: "bg-purple-400",
  completed: "bg-green-400",
  failed: "bg-red-400",
};

export default function Sidebar() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
    } catch {
      return false;
    }
  });
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(
    new Set(),
  );
  const [sessionsByProject, setSessionsByProject] = useState<
    Record<string, SessionRead[]>
  >({});
  const [loadingSessions, setLoadingSessions] = useState<Set<string>>(
    new Set(),
  );

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await fetchProjects();
        if (!cancelled) setProjects(data);
      } catch {
        // Silently fail -- sidebar is supplementary navigation
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
      } catch {
        // localStorage unavailable
      }
      return next;
    });
  }, []);

  const toggleProject = useCallback(
    async (projectId: string) => {
      setExpandedProjects((prev) => {
        const next = new Set(prev);
        if (next.has(projectId)) {
          next.delete(projectId);
        } else {
          next.add(projectId);
        }
        return next;
      });

      // Fetch sessions if not already cached
      if (!sessionsByProject[projectId] && !loadingSessions.has(projectId)) {
        setLoadingSessions((prev) => new Set(prev).add(projectId));
        try {
          const sessions = await fetchSessions(projectId);
          setSessionsByProject((prev) => ({ ...prev, [projectId]: sessions }));
        } catch {
          // Keep empty on error
        } finally {
          setLoadingSessions((prev) => {
            const next = new Set(prev);
            next.delete(projectId);
            return next;
          });
        }
      }
    },
    [sessionsByProject, loadingSessions],
  );

  // Determine active project/session from URL
  const activeProjectId = location.pathname.match(
    /^\/projects\/([^/]+)/,
  )?.[1];
  const activeSessionId = location.pathname.match(
    /^\/sessions\/([^/]+)/,
  )?.[1];

  return (
    <aside
      data-testid="sidebar"
      className={`bg-gray-900 text-white flex-shrink-0 flex flex-col transition-all duration-200 ${
        collapsed ? "w-12" : "w-64"
      }`}
    >
      <div className="p-4 flex items-center justify-between">
        {!collapsed && <h2 className="text-lg font-semibold">Codehive</h2>}
        <button
          onClick={toggleCollapse}
          className="text-gray-400 hover:text-white p-1"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          data-testid="sidebar-toggle"
        >
          {collapsed ? "\u25B6" : "\u25C0"}
        </button>
      </div>
      {!collapsed && (
        <div className="px-4 pb-2">
          <UserMenu />
        </div>
      )}
      <nav className="mt-2 flex-1 overflow-y-auto">
        <ul className="space-y-0.5">
          <li>
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `block px-4 py-2 text-sm ${
                  isActive
                    ? "bg-gray-800 text-white font-medium"
                    : "text-gray-300 hover:bg-gray-800 hover:text-white"
                }`
              }
            >
              {collapsed ? "D" : "Dashboard"}
            </NavLink>
          </li>
          {projects.map((project) => {
            const isActiveProject = activeProjectId === project.id;
            const isExpanded = expandedProjects.has(project.id);
            const sessions = sessionsByProject[project.id];

            return (
              <li key={project.id}>
                <div className="flex items-center">
                  <button
                    onClick={() => toggleProject(project.id)}
                    className="px-2 py-2 text-gray-400 hover:text-white text-xs flex-shrink-0"
                    aria-label={`Toggle ${project.name} sessions`}
                    data-testid={`toggle-${project.id}`}
                  >
                    {isExpanded ? "\u25BC" : "\u25B6"}
                  </button>
                  <NavLink
                    to={`/projects/${project.id}`}
                    className={`flex-1 block py-2 pr-4 text-sm truncate ${
                      isActiveProject
                        ? "text-white font-medium"
                        : "text-gray-300 hover:text-white"
                    }`}
                  >
                    {collapsed
                      ? project.name.charAt(0).toUpperCase()
                      : project.name}
                  </NavLink>
                </div>
                {isExpanded && !collapsed && (
                  <ul className="ml-6 space-y-0.5" data-testid={`sessions-${project.id}`}>
                    {loadingSessions.has(project.id) && (
                      <li className="px-4 py-1 text-xs text-gray-400">
                        Loading...
                      </li>
                    )}
                    {sessions?.map((session) => {
                      const isActiveSession = activeSessionId === session.id;
                      const dotColor =
                        statusDotColors[session.status] ?? "bg-gray-400";
                      return (
                        <li key={session.id}>
                          <NavLink
                            to={`/sessions/${session.id}`}
                            className={`block px-4 py-1.5 text-xs truncate flex items-center gap-2 ${
                              isActiveSession
                                ? "text-white font-medium bg-gray-800"
                                : "text-gray-400 hover:text-white hover:bg-gray-800"
                            }`}
                          >
                            <span
                              className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${dotColor}`}
                              aria-label={session.status}
                            />
                            {session.name}
                          </NavLink>
                        </li>
                      );
                    })}
                    {sessions?.length === 0 && (
                      <li className="px-4 py-1 text-xs text-gray-400">
                        No sessions
                      </li>
                    )}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}
