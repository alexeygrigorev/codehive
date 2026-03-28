import { useState } from "react";
import type { IssueRead, IssueStatus } from "@/api/issues";

export interface IssueListProps {
  issues: IssueRead[];
  statusFilter: IssueStatus | null;
  onFilterChange: (status: IssueStatus | null) => void;
  onCreateIssue: (title: string, description?: string) => Promise<void>;
}

const issueStatusColors: Record<string, string> = {
  open: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  in_progress: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  closed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
};

const filters: { label: string; value: IssueStatus | null }[] = [
  { label: "All", value: null },
  { label: "Open", value: "open" },
  { label: "In Progress", value: "in_progress" },
  { label: "Closed", value: "closed" },
];

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

export default function IssueList({
  issues,
  statusFilter,
  onFilterChange,
  onCreateIssue,
}: IssueListProps) {
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setCreating(true);
    try {
      await onCreateIssue(title.trim(), description.trim() || undefined);
      setTitle("");
      setDescription("");
      setShowForm(false);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="flex gap-1">
          {filters.map((f) => (
            <button
              key={f.label}
              onClick={() => onFilterChange(f.value)}
              className={`px-3 py-1 rounded text-sm font-medium ${
                statusFilter === f.value
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-blue-600 text-white px-3 py-1.5 rounded text-sm"
        >
          + New Task
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="mb-4 p-4 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800"
        >
          <div className="mb-3">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Task title"
              required
              className="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-1.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            />
          </div>
          <div className="mb-3">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Description (optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Task description"
              rows={3}
              className="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-1.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            />
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={creating || !title.trim()}
              className="bg-blue-600 text-white px-3 py-1.5 rounded text-sm disabled:opacity-50"
            >
              {creating ? "Creating..." : "Create Task"}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-3 py-1.5 rounded text-sm"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {issues.length === 0 ? (
        <p className="text-gray-500 dark:text-gray-400 text-sm">No tasks found.</p>
      ) : (
        <ul className="divide-y divide-gray-200 dark:divide-gray-700 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800">
          {issues.map((issue) => {
            const colorClass =
              issueStatusColors[issue.status] ?? "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300";
            return (
              <li key={issue.id} className="px-4 py-3">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-gray-900 dark:text-gray-100">
                    {issue.title}
                  </span>
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colorClass}`}
                  >
                    {issue.status}
                  </span>
                </div>
                <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  {formatRelativeTime(issue.created_at)}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
