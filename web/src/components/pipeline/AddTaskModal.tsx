import { useState } from "react";
import { addTask } from "@/api/pipeline";

interface AddTaskModalProps {
  projectId: string;
  onClose: () => void;
  onTaskAdded: () => void;
}

export default function AddTaskModal({
  projectId,
  onClose,
  onTaskAdded,
}: AddTaskModalProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [acceptanceCriteria, setAcceptanceCriteria] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;

    setSubmitting(true);
    setError(null);

    try {
      await addTask({
        project_id: projectId,
        title: title.trim(),
        description: description.trim() || undefined,
        acceptance_criteria: acceptanceCriteria.trim() || undefined,
      });
      onTaskAdded();
      onClose();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to add task",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        data-testid="add-task-backdrop"
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />

      {/* Modal */}
      <div
        data-testid="add-task-modal"
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div className="bg-gray-900 dark:bg-gray-900 border border-gray-700 rounded-lg shadow-xl w-full max-w-md">
          <div className="flex items-center justify-between p-4 border-b border-gray-700">
            <h2 className="text-lg font-semibold text-gray-100">
              Add Task to Backlog
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white"
              data-testid="add-task-close"
            >
              x
            </button>
          </div>

          <form onSubmit={handleSubmit} className="p-4 space-y-4">
            {/* Title */}
            <div>
              <label
                htmlFor="task-title"
                className="block text-sm font-medium text-gray-300 mb-1"
              >
                Title *
              </label>
              <input
                id="task-title"
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3 py-2 bg-gray-800 text-white border border-gray-600 rounded focus:border-blue-500 focus:outline-none text-sm"
                placeholder="Task title"
                data-testid="add-task-title-input"
              />
            </div>

            {/* Description */}
            <div>
              <label
                htmlFor="task-description"
                className="block text-sm font-medium text-gray-300 mb-1"
              >
                Description
              </label>
              <textarea
                id="task-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full px-3 py-2 bg-gray-800 text-white border border-gray-600 rounded focus:border-blue-500 focus:outline-none text-sm"
                placeholder="Optional description"
                rows={3}
                data-testid="add-task-description-input"
              />
            </div>

            {/* Acceptance Criteria */}
            <div>
              <label
                htmlFor="task-ac"
                className="block text-sm font-medium text-gray-300 mb-1"
              >
                Acceptance Criteria
              </label>
              <textarea
                id="task-ac"
                value={acceptanceCriteria}
                onChange={(e) => setAcceptanceCriteria(e.target.value)}
                className="w-full px-3 py-2 bg-gray-800 text-white border border-gray-600 rounded focus:border-blue-500 focus:outline-none text-sm"
                placeholder="Optional acceptance criteria"
                rows={3}
                data-testid="add-task-ac-input"
              />
            </div>

            {error && (
              <p className="text-red-400 text-sm" data-testid="add-task-error">
                {error}
              </p>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm text-gray-300 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !title.trim()}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="add-task-submit"
              >
                {submitting ? "Creating..." : "Create"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
}
