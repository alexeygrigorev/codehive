import { useEffect, useState } from "react";
import { fetchRoles, deleteRole } from "@/api/roles";
import type { RoleRead } from "@/api/roles";

interface RoleListProps {
  onEdit?: (role: RoleRead) => void;
  onCreate?: () => void;
}

export default function RoleList({ onEdit, onCreate }: RoleListProps) {
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchRoles();
        if (!cancelled) {
          setRoles(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to fetch roles",
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
  }, []);

  async function handleDelete(roleName: string) {
    try {
      await deleteRole(roleName);
      setRoles((prev) => prev.filter((r) => r.name !== roleName));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to delete role",
      );
    }
  }

  if (loading) {
    return <p className="text-gray-500 dark:text-gray-400">Loading roles...</p>;
  }

  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Roles</h2>
        <button
          type="button"
          className="rounded bg-green-500 px-3 py-1 text-sm text-white hover:bg-green-600"
          onClick={onCreate}
        >
          Create Role
        </button>
      </div>
      {roles.length === 0 ? (
        <p className="text-gray-500 dark:text-gray-400">No roles</p>
      ) : (
        <ul className="space-y-2">
          {roles.map((role) => (
            <li
              key={role.name}
              className="flex items-center justify-between rounded border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm"
            >
              <div>
                <span className="font-medium">{role.name}</span>
                {role.description && (
                  <span className="ml-2 text-gray-500 dark:text-gray-400">
                    {role.description}
                  </span>
                )}
                <span
                  className={`ml-2 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                    role.is_builtin
                      ? "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300"
                      : "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200"
                  }`}
                >
                  {role.is_builtin ? "Built-in" : "Custom"}
                </span>
              </div>
              {!role.is_builtin && (
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="rounded bg-blue-500 px-2 py-1 text-xs text-white hover:bg-blue-600"
                    onClick={() => onEdit?.(role)}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="rounded bg-red-500 px-2 py-1 text-xs text-white hover:bg-red-600"
                    onClick={() => handleDelete(role.name)}
                  >
                    Delete
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
