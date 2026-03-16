import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { searchAll } from "@/api/search";
import type { SearchResultItem } from "@/api/search";

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const performSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      setShowDropdown(false);
      return;
    }
    setLoading(true);
    try {
      const response = await searchAll(q, { limit: 5 });
      setResults(response.results);
      setShowDropdown(true);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    if (!query.trim()) {
      setResults([]);
      setShowDropdown(false);
      return;
    }
    timerRef.current = setTimeout(() => {
      performSearch(query);
    }, 300);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [query, performSearch]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && query.trim()) {
      setShowDropdown(false);
      navigate(`/search?q=${encodeURIComponent(query.trim())}`);
    }
  }

  function handleResultClick(result: SearchResultItem) {
    setShowDropdown(false);
    setQuery("");
    switch (result.entity_type) {
      case "session":
        navigate(`/sessions/${result.entity_id}`);
        break;
      case "message":
        navigate(
          `/sessions/${result.session_id ?? result.entity_id}`,
        );
        break;
      case "issue":
        navigate(
          `/projects/${result.project_id ?? "unknown"}`,
        );
        break;
      case "event":
        navigate(
          `/sessions/${result.session_id ?? result.entity_id}`,
        );
        break;
    }
  }

  function handleSeeAll() {
    setShowDropdown(false);
    navigate(`/search?q=${encodeURIComponent(query.trim())}`);
  }

  return (
    <div ref={containerRef} className="relative" data-testid="search-bar">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Search..."
        className="w-64 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        aria-label="Search"
      />
      {showDropdown && (
        <div
          className="absolute top-full left-0 mt-1 w-80 rounded-md border border-gray-200 bg-white shadow-lg z-50"
          data-testid="search-dropdown"
        >
          {loading && (
            <div className="p-3 text-sm text-gray-500">Searching...</div>
          )}
          {!loading && results.length === 0 && (
            <div className="p-3 text-sm text-gray-500">No results</div>
          )}
          {!loading &&
            results.map((result) => (
              <button
                key={result.id}
                type="button"
                className="w-full text-left px-3 py-2 hover:bg-gray-50 border-b border-gray-100 last:border-b-0"
                onClick={() => handleResultClick(result)}
                data-testid="dropdown-result"
              >
                <span className="text-xs font-medium text-gray-500 uppercase">
                  {result.entity_type}
                </span>
                <p className="text-sm text-gray-700 truncate">
                  {result.snippet}
                </p>
              </button>
            ))}
          {!loading && results.length > 0 && (
            <button
              type="button"
              className="w-full text-center px-3 py-2 text-sm text-blue-600 hover:bg-gray-50"
              onClick={handleSeeAll}
              data-testid="see-all-results"
            >
              See all results
            </button>
          )}
        </div>
      )}
    </div>
  );
}
