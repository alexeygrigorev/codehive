import { Link } from "react-router-dom";

export interface ProjectCardProps {
  id: string;
  name: string;
  description: string | null;
  archetype: string | null;
  sessionCount: number;
}

export default function ProjectCard({
  id,
  name,
  description,
  archetype,
  sessionCount,
}: ProjectCardProps) {
  const truncated =
    description && description.length > 120
      ? description.slice(0, 120) + "..."
      : description;

  return (
    <Link
      to={`/projects/${id}`}
      className="block rounded-lg border border-gray-200 bg-white p-4 shadow-sm hover:shadow-md transition-shadow"
    >
      <div className="flex items-start justify-between">
        <h3 className="text-lg font-semibold text-gray-900">{name}</h3>
        {archetype && (
          <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
            {archetype}
          </span>
        )}
      </div>
      {truncated && <p className="mt-1 text-sm text-gray-600">{truncated}</p>}
      <div className="mt-3 text-xs text-gray-500">
        {sessionCount} {sessionCount === 1 ? "session" : "sessions"}
      </div>
    </Link>
  );
}
