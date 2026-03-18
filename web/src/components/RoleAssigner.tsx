import { useEffect, useState } from "react";
import { fetchRoles } from "@/api/roles";
import type { RoleRead } from "@/api/roles";

interface RoleAssignerProps {
  value?: string;
  onChange?: (roleName: string) => void;
}

export default function RoleAssigner({ value, onChange }: RoleAssignerProps) {
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await fetchRoles();
        if (!cancelled) {
          setRoles(data);
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

  if (loading) {
    return <p className="text-gray-500 dark:text-gray-400">Loading roles...</p>;
  }

  return (
    <select
      value={value ?? ""}
      onChange={(e) => onChange?.(e.target.value)}
      className="rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1 text-sm"
      aria-label="Select role"
    >
      <option value="">Select a role...</option>
      {roles.map((role) => (
        <option key={role.name} value={role.name}>
          {role.display_name || role.name}
        </option>
      ))}
    </select>
  );
}
