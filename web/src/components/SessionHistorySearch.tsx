import { useState, useEffect, useRef } from "react";
import { searchSessionHistory } from "@/api/search";
import type { SessionHistoryItem } from "@/api/search";

interface SessionHistorySearchProps {
  sessionId: string;
}

export default function SessionHistorySearch({
  sessionId,
}: SessionHistorySearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SessionHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);

    if (!query.trim()) {
      setResults([]);
      setSearched(false);
      return;
    }

    timerRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const response = await searchSessionHistory(sessionId, query);
        setResults(response.results);
        setSearched(true);
      } catch {
        setResults([]);
        setSearched(true);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [query, sessionId]);

  return (
    <div className="border-b border-gray-200 px-4 py-2" data-testid="session-history-search">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search messages..."
        className="w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        aria-label="Search session messages"
      />
      {loading && (
        <p className="text-xs text-gray-500 mt-1">Searching...</p>
      )}
      {!loading && searched && results.length === 0 && (
        <p className="text-xs text-gray-500 mt-1">No matching messages</p>
      )}
      {!loading && results.length > 0 && (
        <ul className="mt-2 space-y-1 max-h-48 overflow-y-auto">
          {results.map((item) => (
            <li
              key={item.id}
              className="rounded bg-gray-50 px-2 py-1 text-sm"
              data-testid="history-result"
            >
              <span className="text-xs font-medium text-gray-500 mr-1">
                {item.role}:
              </span>
              <span className="text-gray-700">{item.content}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
