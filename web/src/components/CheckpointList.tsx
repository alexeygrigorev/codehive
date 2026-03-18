import { useEffect, useState } from "react";
import { fetchCheckpoints, rollbackCheckpoint } from "@/api/checkpoints";
import type { CheckpointRead } from "@/api/checkpoints";
import CheckpointCreate from "./CheckpointCreate";

interface CheckpointListProps {
  sessionId: string;
}

export default function CheckpointList({ sessionId }: CheckpointListProps) {
  const [checkpoints, setCheckpoints] = useState<CheckpointRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchCheckpoints(sessionId);
      setCheckpoints(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch checkpoints",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function initialLoad() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchCheckpoints(sessionId);
        if (!cancelled) {
          setCheckpoints(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to fetch checkpoints",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    initialLoad();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  async function handleRestore(checkpointId: string) {
    try {
      await rollbackCheckpoint(checkpointId);
      await load();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to rollback checkpoint",
      );
    }
  }

  if (loading) {
    return <p className="text-gray-500 dark:text-gray-400">Loading checkpoints...</p>;
  }

  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  return (
    <div>
      <CheckpointCreate sessionId={sessionId} onCreated={load} />
      {checkpoints.length === 0 ? (
        <p className="text-gray-500 dark:text-gray-400">No checkpoints</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {checkpoints.map((cp) => (
            <li
              key={cp.id}
              className="flex items-center justify-between rounded border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm"
            >
              <div>
                <span className="font-medium">
                  {cp.label ?? cp.id}
                </span>
                {cp.git_ref && (
                  <span className="ml-2 text-xs text-gray-400">
                    {cp.git_ref}
                  </span>
                )}
                <span className="ml-2 text-xs text-gray-400">
                  {cp.created_at}
                </span>
              </div>
              <button
                type="button"
                className="rounded bg-blue-500 px-2 py-1 text-xs text-white hover:bg-blue-600"
                onClick={() => handleRestore(cp.id)}
              >
                Restore
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
