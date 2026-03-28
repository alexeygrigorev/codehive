interface RoleBadgeProps {
  role: string | null | undefined;
  className?: string;
}

interface RoleInfo {
  label: string;
  displayName: string;
  colors: string;
}

const ROLE_MAP: Record<string, RoleInfo> = {
  pm: {
    label: "PM",
    displayName: "Product Manager",
    colors:
      "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  },
  swe: {
    label: "SWE",
    displayName: "Software Engineer",
    colors:
      "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  },
  qa: {
    label: "QA",
    displayName: "QA Tester",
    colors:
      "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
  },
  oncall: {
    label: "OnCall",
    displayName: "On-Call Engineer",
    colors:
      "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  },
};

const FALLBACK_COLORS =
  "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200";

export default function RoleBadge({ role, className }: RoleBadgeProps) {
  if (role == null) return null;

  const info = ROLE_MAP[role];
  const label = info?.label ?? role;
  const displayName = info?.displayName ?? role;
  const colors = info?.colors ?? FALLBACK_COLORS;

  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colors}${className ? ` ${className}` : ""}`}
      title={displayName}
      data-testid="role-badge"
    >
      {label}
    </span>
  );
}
