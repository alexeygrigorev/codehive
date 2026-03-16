import { Link } from "react-router-dom";
import type { SearchResultItem } from "@/api/search";
import SearchHighlight from "./SearchHighlight";

interface SearchResultProps {
  result: SearchResultItem;
  query: string;
}

const TYPE_LABELS: Record<string, string> = {
  session: "Session",
  message: "Message",
  issue: "Issue",
  event: "Event",
};

const TYPE_COLORS: Record<string, string> = {
  session: "bg-blue-100 text-blue-800",
  message: "bg-green-100 text-green-800",
  issue: "bg-yellow-100 text-yellow-800",
  event: "bg-purple-100 text-purple-800",
};

function getResultUrl(result: SearchResultItem): string {
  switch (result.entity_type) {
    case "session":
      return `/sessions/${result.entity_id}`;
    case "message":
      return result.session_id
        ? `/sessions/${result.session_id}`
        : `/sessions/${result.entity_id}`;
    case "issue":
      return result.project_id
        ? `/projects/${result.project_id}`
        : `/projects/unknown`;
    case "event":
      return result.session_id
        ? `/sessions/${result.session_id}`
        : `/sessions/${result.entity_id}`;
    default:
      return "/";
  }
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export default function SearchResult({ result, query }: SearchResultProps) {
  const url = getResultUrl(result);
  const typeLabel = TYPE_LABELS[result.entity_type] ?? result.entity_type;
  const typeColor =
    TYPE_COLORS[result.entity_type] ?? "bg-gray-100 text-gray-800";

  return (
    <Link
      to={url}
      className="search-result block rounded-lg border border-gray-200 p-4 hover:bg-gray-50 transition-colors"
      data-testid="search-result"
    >
      <div className="flex items-center gap-2 mb-1">
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${typeColor}`}
          data-testid="type-badge"
        >
          {typeLabel}
        </span>
        {result.project_name && (
          <span className="text-xs text-gray-500">{result.project_name}</span>
        )}
        <span className="text-xs text-gray-400 ml-auto">
          {formatTimestamp(result.created_at)}
        </span>
      </div>
      <p className="text-sm text-gray-700">
        <SearchHighlight text={result.snippet} query={query} />
      </p>
    </Link>
  );
}
