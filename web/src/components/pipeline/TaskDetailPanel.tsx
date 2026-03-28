import { useEffect, useState } from "react";
import type {
  PipelineTask,
  PipelineLogEntry,
  IssueLogEntry,
} from "@/api/pipeline";
import { fetchTaskPipelineLog, fetchIssueLogEntries } from "@/api/pipeline";

interface TaskDetailPanelProps {
  task: PipelineTask;
  onClose: () => void;
}

export default function TaskDetailPanel({
  task,
  onClose,
}: TaskDetailPanelProps) {
  const [pipelineLog, setPipelineLog] = useState<PipelineLogEntry[]>([]);
  const [logLoading, setLogLoading] = useState(true);
  const [issueLog, setIssueLog] = useState<IssueLogEntry[]>([]);
  const [issueLogLoading, setIssueLogLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadLog() {
      try {
        const log = await fetchTaskPipelineLog(task.id);
        if (!cancelled) setPipelineLog(log);
      } catch {
        // Log may not exist yet
      } finally {
        if (!cancelled) setLogLoading(false);
      }
    }

    loadLog();
    return () => {
      cancelled = true;
    };
  }, [task.id]);

  useEffect(() => {
    if (!task.issue_id) return;

    let cancelled = false;
    setIssueLogLoading(true);

    async function loadIssueLog() {
      try {
        const entries = await fetchIssueLogEntries(task.issue_id!);
        if (!cancelled) setIssueLog(entries);
      } catch {
        // Issue logs may not be available
      } finally {
        if (!cancelled) setIssueLogLoading(false);
      }
    }

    loadIssueLog();
    return () => {
      cancelled = true;
    };
  }, [task.issue_id]);

  return (
    <>
      {/* Backdrop */}
      <div
        data-testid="task-detail-backdrop"
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />

      {/* Panel */}
      <div
        data-testid="task-detail-panel"
        className="fixed right-0 top-0 h-full w-full max-w-lg bg-gray-900 dark:bg-gray-900 border-l border-gray-700 z-50 overflow-y-auto shadow-xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-gray-100">Task Detail</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-xl"
            data-testid="task-detail-close"
          >
            x
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Title */}
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-1">Title</h3>
            <p className="text-gray-100">{task.title}</p>
          </div>

          {/* Instructions */}
          {task.instructions && (
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-1">
                Instructions
              </h3>
              <p className="text-gray-300 text-sm whitespace-pre-wrap">
                {task.instructions}
              </p>
            </div>
          )}

          {/* Pipeline Status */}
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-1">
              Pipeline Status
            </h3>
            <span className="text-sm text-gray-200 bg-gray-700 px-2 py-1 rounded">
              {task.pipeline_status}
            </span>
          </div>

          {/* Pipeline History Log */}
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-1">
              Pipeline History
            </h3>
            {logLoading ? (
              <p className="text-gray-500 text-sm">Loading...</p>
            ) : pipelineLog.length === 0 ? (
              <p className="text-gray-500 text-sm">No transitions yet</p>
            ) : (
              <ul className="space-y-2">
                {pipelineLog.map((entry) => (
                  <li
                    key={entry.id}
                    className="text-sm text-gray-300 border-l-2 border-gray-600 pl-3"
                  >
                    <span className="text-gray-400">
                      {new Date(entry.created_at).toLocaleString()}
                    </span>
                    <br />
                    <span>
                      {entry.from_status} → {entry.to_status}
                    </span>
                    {entry.actor && (
                      <span className="text-gray-500 ml-2">
                        by {entry.actor}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Issue Log Entries */}
          {task.issue_id && (
            <div data-testid="issue-log-section">
              <h3 className="text-sm font-medium text-gray-400 mb-1">
                Task Log
              </h3>
              {issueLogLoading ? (
                <p className="text-gray-500 text-sm">Loading task logs...</p>
              ) : issueLog.length === 0 ? (
                <p className="text-gray-500 text-sm">No task log entries</p>
              ) : (
                <ul className="space-y-2">
                  {issueLog.map((entry) => (
                    <li
                      key={entry.id}
                      data-testid="issue-log-entry"
                      className="text-sm text-gray-300 border-l-2 border-blue-600 pl-3"
                    >
                      <div className="flex items-center gap-2">
                        {entry.agent_avatar_url && (
                          <img
                            src={entry.agent_avatar_url}
                            alt={entry.agent_name ?? entry.agent_role}
                            className="w-8 h-8 rounded-full"
                            data-testid="agent-avatar"
                          />
                        )}
                        <span className="text-gray-400">
                          {new Date(entry.created_at).toLocaleString()}
                        </span>
                        <span className="text-blue-400">
                          {entry.agent_name
                            ? `${entry.agent_name} [${entry.agent_role}]`
                            : `[${entry.agent_role}]`}
                        </span>
                      </div>
                      <p className="text-gray-300 mt-1 whitespace-pre-wrap">
                        {entry.content}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
