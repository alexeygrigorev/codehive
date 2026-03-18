import { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { WebSocketProvider } from "@/context/WebSocketContext";
import { apiClient } from "@/api/client";
import type { SessionRead } from "@/api/sessions";
import { fetchProject, type ProjectRead } from "@/api/projects";
import Breadcrumb from "@/components/Breadcrumb";
import ChatPanel from "@/components/ChatPanel";
import SidebarTabs from "@/components/sidebar/SidebarTabs";
import SessionModeIndicator from "@/components/SessionModeIndicator";
import SessionModeSwitcher from "@/components/SessionModeSwitcher";
import SessionApprovalBadge from "@/components/SessionApprovalBadge";
import { useResponsive } from "@/hooks/useResponsive";

const SIDEBAR_STORAGE_KEY = "session-sidebar-collapsed";

function getSidebarCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function setSidebarCollapsed(collapsed: boolean): void {
  try {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, String(collapsed));
  } catch {
    // localStorage unavailable
  }
}

export default function SessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { isMobile } = useResponsive();
  const [session, setSession] = useState<SessionRead | null>(null);
  const [project, setProject] = useState<ProjectRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modeLoading, setModeLoading] = useState(false);
  const [showModeSwitcher, setShowModeSwitcher] = useState(false);
  const [sidebarCollapsed, _setSidebarCollapsed] = useState(
    getSidebarCollapsed,
  );

  function toggleSidebar() {
    _setSidebarCollapsed((prev) => {
      const next = !prev;
      setSidebarCollapsed(next);
      return next;
    });
  }

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;

    async function load() {
      try {
        const response = await apiClient.get(`/api/sessions/${sessionId}`);
        if (!response.ok) {
          throw new Error(`Failed to load session: ${response.status}`);
        }
        const data = (await response.json()) as SessionRead;
        if (!cancelled) {
          setSession(data);
          // Fetch parent project for breadcrumb and header
          if (data.project_id) {
            try {
              const proj = await fetchProject(data.project_id);
              if (!cancelled) setProject(proj);
            } catch {
              // Project fetch failure is non-critical
            }
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load session",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const handleModeChange = useCallback(
    async (newMode: string) => {
      if (!sessionId) return;
      setModeLoading(true);
      try {
        const response = await apiClient.patch(`/api/sessions/${sessionId}`, {
          mode: newMode,
        });
        if (!response.ok) {
          throw new Error(`Failed to update mode: ${response.status}`);
        }
        setSession((prev) => (prev ? { ...prev, mode: newMode } : prev));
        setShowModeSwitcher(false);
      } finally {
        setModeLoading(false);
      }
    },
    [sessionId],
  );

  if (loading) {
    return (
      <div>
        <h1 className="text-2xl font-bold dark:text-gray-100">Session</h1>
        <p className="text-gray-500 mt-4">Loading session...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <h1 className="text-2xl font-bold dark:text-gray-100">Session</h1>
        <p className="text-red-600 mt-4">{error}</p>
      </div>
    );
  }

  if (!session || !sessionId) {
    return (
      <div>
        <h1 className="text-2xl font-bold dark:text-gray-100">Session</h1>
        <p className="text-red-600 mt-4">Session not found</p>
      </div>
    );
  }

  const statusColors: Record<string, string> = {
    idle: "bg-gray-100 text-gray-700",
    planning: "bg-yellow-100 text-yellow-800",
    executing: "bg-blue-100 text-blue-800",
    waiting_input: "bg-purple-100 text-purple-800",
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
  };

  const statusClass =
    statusColors[session.status] ?? "bg-gray-100 text-gray-700";

  return (
    <WebSocketProvider sessionId={sessionId}>
      <div className="flex h-full flex-col">
        {project && (
          <div className="px-4 pt-3">
            <Breadcrumb
              segments={[
                { label: "Dashboard", to: "/" },
                { label: project.name, to: `/projects/${project.id}` },
                { label: session.name, to: `/sessions/${session.id}` },
              ]}
            />
          </div>
        )}
        <div
          className="flex items-center justify-between border-b border-gray-200 dark:border-gray-700 px-4 py-2"
          data-testid="session-header"
        >
          {/* Left group: project name link + session name + status */}
          <div className="flex items-center gap-2">
            {project && (
              <>
                <Link
                  to={`/projects/${project.id}`}
                  className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:underline"
                  data-testid="project-link"
                >
                  {project.name}
                </Link>
                <span className="text-gray-300 dark:text-gray-600">/</span>
              </>
            )}
            <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">{session.name}</h1>
            <span
              className={`session-status inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusClass}`}
            >
              {session.status}
            </span>
          </div>
          {/* Right group: mode indicator + approval badge */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="mode-indicator-button"
              onClick={() => setShowModeSwitcher((prev) => !prev)}
              aria-label="Toggle mode switcher"
            >
              <SessionModeIndicator mode={session.mode} />
            </button>
            <SessionApprovalBadge />
          </div>
        </div>
        {showModeSwitcher && (
          <div className="border-b border-gray-200 dark:border-gray-700 px-4 py-2">
            <SessionModeSwitcher
              currentMode={session.mode}
              onModeChange={handleModeChange}
              loading={modeLoading}
            />
          </div>
        )}
        <div
          className={
            isMobile
              ? "flex flex-col flex-1 min-h-0"
              : "flex flex-1 min-h-0"
          }
          data-testid="session-content"
        >
          <div className={isMobile ? "" : "flex-1 min-w-0"}>
            <ChatPanel sessionId={sessionId} />
          </div>
          {isMobile ? (
            <div className="border-t border-gray-200 dark:border-gray-700">
              <details className="session-sidebar-toggle">
                <summary className="px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 cursor-pointer">
                  Sidebar
                </summary>
                <SidebarTabs sessionId={sessionId} />
              </details>
            </div>
          ) : (
            <div
              className="border-l border-gray-200 dark:border-gray-700 flex flex-shrink-0 transition-all duration-200"
              style={{ width: sidebarCollapsed ? 32 : 320 }}
              data-testid="session-sidebar"
            >
              <button
                type="button"
                onClick={toggleSidebar}
                className="flex items-center justify-center w-8 flex-shrink-0 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 border-r border-gray-200 dark:border-gray-700"
                aria-label={
                  sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"
                }
                data-testid="sidebar-toggle"
              >
                {sidebarCollapsed ? "\u25C0" : "\u25B6"}
              </button>
              {!sidebarCollapsed && (
                <div className="flex-1 min-w-0 overflow-hidden">
                  <SidebarTabs sessionId={sessionId} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </WebSocketProvider>
  );
}
