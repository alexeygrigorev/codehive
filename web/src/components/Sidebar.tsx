import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  fetchProjects,
  fetchArchivedProjects,
  type ProjectRead,
} from "@/api/projects";

const SIDEBAR_COLLAPSED_KEY = "codehive-sidebar-collapsed";

type TimeGroup =
  | "Today"
  | "Yesterday"
  | "Previous 7 days"
  | "Previous 30 days"
  | "Older";

const TIME_GROUP_ORDER: TimeGroup[] = [
  "Today",
  "Yesterday",
  "Previous 7 days",
  "Previous 30 days",
  "Older",
];

function getTimeGroup(createdAt: string): TimeGroup {
  const created = new Date(createdAt);
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayStart = new Date(todayStart);
  yesterdayStart.setDate(yesterdayStart.getDate() - 1);
  const sevenDaysAgo = new Date(todayStart);
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
  const thirtyDaysAgo = new Date(todayStart);
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

  if (created >= todayStart) return "Today";
  if (created >= yesterdayStart) return "Yesterday";
  if (created >= sevenDaysAgo) return "Previous 7 days";
  if (created >= thirtyDaysAgo) return "Previous 30 days";
  return "Older";
}

function groupProjectsByTime(
  projects: ProjectRead[],
): Map<TimeGroup, ProjectRead[]> {
  const groups = new Map<TimeGroup, ProjectRead[]>();
  for (const group of TIME_GROUP_ORDER) {
    groups.set(group, []);
  }
  for (const project of projects) {
    const group = getTimeGroup(project.created_at);
    groups.get(group)!.push(project);
  }
  // Sort each group by created_at descending (most recent first)
  for (const [, list] of groups) {
    list.sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
  }
  return groups;
}

export default function Sidebar() {
  const location = useLocation();
  const searchRef = useRef<HTMLInputElement>(null);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
    } catch {
      return false;
    }
  });
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [archivedCount, setArchivedCount] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [collapsedGroups, setCollapsedGroups] = useState<Set<TimeGroup>>(
    new Set(),
  );

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [data, archived] = await Promise.all([
          fetchProjects(),
          fetchArchivedProjects(),
        ]);
        if (!cancelled) {
          setProjects(data);
          setArchivedCount(archived.length);
        }
      } catch {
        // Silently fail -- sidebar is supplementary navigation
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  // Keyboard shortcut: Ctrl+K or / to focus search
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (
        (e.key === "k" && (e.ctrlKey || e.metaKey)) ||
        (e.key === "/" &&
          !(e.target instanceof HTMLInputElement) &&
          !(e.target instanceof HTMLTextAreaElement))
      ) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
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

  const toggleGroup = useCallback((group: TimeGroup) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(group)) {
        next.delete(group);
      } else {
        next.add(group);
      }
      return next;
    });
  }, []);

  // Filter projects by search query
  const filteredProjects = useMemo(() => {
    if (!searchQuery.trim()) return projects;
    const q = searchQuery.toLowerCase();
    return projects.filter((p) => p.name.toLowerCase().includes(q));
  }, [projects, searchQuery]);

  // Group filtered projects by time
  const groupedProjects = useMemo(
    () => groupProjectsByTime(filteredProjects),
    [filteredProjects],
  );

  // Determine active project from URL
  const activeProjectId = location.pathname.match(
    /^\/projects\/([^/]+)/,
  )?.[1];

  const totalCount = projects.length;
  const filteredCount = filteredProjects.length;
  const isFiltering = searchQuery.trim().length > 0;

  const countLabel = isFiltering
    ? `Projects (${filteredCount} of ${totalCount})`
    : `Projects (${totalCount})`;

  return (
    <aside
      data-testid="sidebar"
      className={`bg-gray-900 text-white flex-shrink-0 flex flex-col min-h-0 overflow-hidden transition-all duration-200 ${
        collapsed ? "w-12" : "w-64"
      }`}
    >
      {/* Header */}
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

      {/* Navigation links */}
      <nav className="flex flex-col">
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
        <NavLink
          to="/usage"
          className={({ isActive }) =>
            `block px-4 py-2 text-sm ${
              isActive
                ? "bg-gray-800 text-white font-medium"
                : "text-gray-300 hover:bg-gray-800 hover:text-white"
            }`
          }
        >
          {collapsed ? "U" : "Usage"}
        </NavLink>
        <NavLink
          to="/pipeline"
          className={({ isActive }) =>
            `block px-4 py-2 text-sm ${
              isActive
                ? "bg-gray-800 text-white font-medium"
                : "text-gray-300 hover:bg-gray-800 hover:text-white"
            }`
          }
        >
          {collapsed ? "P" : "Pipeline"}
        </NavLink>
      </nav>

      {!collapsed && (
        <>
          {/* Project count header */}
          <div
            className="px-4 pt-4 pb-2 text-xs text-gray-400 uppercase tracking-wider"
            data-testid="sidebar-project-count"
          >
            {countLabel}
          </div>

          {/* Search input */}
          <div className="px-4 pb-2">
            <input
              ref={searchRef}
              type="text"
              placeholder="Search projects... (Ctrl+K)"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3 py-1.5 text-sm bg-gray-800 text-white placeholder-gray-500 rounded border border-gray-700 focus:border-blue-500 focus:outline-none"
              data-testid="sidebar-search"
            />
          </div>

          {/* New Project button */}
          <div className="px-4 pb-2">
            <NavLink
              to="/projects/new"
              className="block w-full text-center px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded"
              data-testid="sidebar-new-project"
            >
              + New Project
            </NavLink>
          </div>
        </>
      )}

      {/* Project list */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {!collapsed && projects.length === 0 && (
          <div className="px-4 py-4 text-sm text-gray-400">
            No projects yet
          </div>
        )}

        {!collapsed && projects.length > 0 && filteredProjects.length === 0 && (
          <div className="px-4 py-4 text-sm text-gray-400">
            No matching projects
          </div>
        )}

        {!collapsed &&
          TIME_GROUP_ORDER.map((group) => {
            const groupProjects = groupedProjects.get(group) ?? [];
            if (groupProjects.length === 0) return null;
            const isGroupCollapsed = collapsedGroups.has(group);
            const groupSlug = group.toLowerCase().replace(/\s+/g, "-");

            return (
              <div key={group} data-testid={`time-group-${groupSlug}`}>
                <button
                  onClick={() => toggleGroup(group)}
                  className="w-full flex items-center px-4 py-1.5 text-xs text-gray-400 uppercase tracking-wider hover:text-gray-200"
                  data-testid={`time-group-toggle-${groupSlug}`}
                >
                  <span className="mr-1.5 text-[10px]">
                    {isGroupCollapsed ? "\u25B6" : "\u25BC"}
                  </span>
                  {group}
                </button>
                {!isGroupCollapsed && (
                  <ul className="space-y-0.5">
                    {groupProjects.map((project) => {
                      const isActive = activeProjectId === project.id;
                      return (
                        <li key={project.id}>
                          <NavLink
                            to={`/projects/${project.id}`}
                            className={`block px-4 py-2 text-sm truncate ${
                              isActive
                                ? "bg-gray-800 text-white font-medium"
                                : "text-gray-300 hover:bg-gray-800 hover:text-white"
                            }`}
                          >
                            {project.name}
                          </NavLink>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            );
          })}

        {collapsed &&
          projects.map((project) => (
            <NavLink
              key={project.id}
              to={`/projects/${project.id}`}
              className={`block px-2 py-2 text-xs text-center truncate ${
                activeProjectId === project.id
                  ? "bg-gray-800 text-white font-medium"
                  : "text-gray-300 hover:bg-gray-800 hover:text-white"
              }`}
              title={project.name}
            >
              {project.name.charAt(0).toUpperCase()}
            </NavLink>
          ))}

        {!collapsed && archivedCount > 0 && (
          <div className="px-4 py-2 border-t border-gray-700">
            <NavLink
              to="/projects/archived"
              className="text-sm text-gray-400 hover:text-white"
              data-testid="sidebar-archived-link"
            >
              Archived ({archivedCount})
            </NavLink>
          </div>
        )}
      </div>
    </aside>
  );
}
