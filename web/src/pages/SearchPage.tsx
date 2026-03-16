import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { searchAll } from "@/api/search";
import type { SearchResultItem, EntityType } from "@/api/search";
import SearchResult from "@/components/search/SearchResult";

const TABS: { label: string; type: EntityType | null }[] = [
  { label: "All", type: null },
  { label: "Sessions", type: "session" },
  { label: "Messages", type: "message" },
  { label: "Issues", type: "issue" },
  { label: "Events", type: "event" },
];

const PAGE_SIZE = 20;

export default function SearchPage() {
  const [searchParams] = useSearchParams();
  const query = searchParams.get("q") ?? "";

  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<EntityType | null>(null);
  const [offset, setOffset] = useState(0);

  const doSearch = useCallback(
    async (q: string, type: EntityType | null, searchOffset: number) => {
      if (!q.trim()) return;
      setLoading(true);
      try {
        const response = await searchAll(q, {
          type: type ?? undefined,
          limit: PAGE_SIZE,
          offset: searchOffset,
        });
        if (searchOffset === 0) {
          setResults(response.results);
        } else {
          setResults((prev) => [...prev, ...response.results]);
        }
        setTotal(response.total);
        setHasMore(response.has_more);
      } catch {
        if (searchOffset === 0) {
          setResults([]);
        }
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    setResults([]);
    setOffset(0);
    setHasMore(false);
    doSearch(query, activeTab, 0);
  }, [query, activeTab, doSearch]);

  function handleTabClick(type: EntityType | null) {
    setActiveTab(type);
  }

  function handleLoadMore() {
    const newOffset = offset + PAGE_SIZE;
    setOffset(newOffset);
    doSearch(query, activeTab, newOffset);
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Search Results</h1>
      {query && (
        <p className="text-gray-600 mb-4">
          Results for &quot;{query}&quot;
          {total > 0 && (
            <span className="text-gray-400 ml-2">({total} found)</span>
          )}
        </p>
      )}

      <div className="flex gap-1 mb-6 border-b border-gray-200" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.label}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.type}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.type
                ? "border-blue-500 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
            onClick={() => handleTabClick(tab.type)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading && results.length === 0 && (
        <div className="text-center py-8" data-testid="search-loading">
          <p className="text-gray-500">Searching...</p>
        </div>
      )}

      {!loading && results.length === 0 && query && (
        <div className="text-center py-8" data-testid="search-empty">
          <p className="text-gray-500">No results found</p>
        </div>
      )}

      <div className="space-y-3">
        {results.map((result) => (
          <SearchResult key={result.id} result={result} query={query} />
        ))}
      </div>

      {hasMore && (
        <div className="text-center mt-6">
          <button
            type="button"
            className="px-4 py-2 text-sm font-medium text-blue-600 bg-blue-50 rounded-md hover:bg-blue-100 transition-colors"
            onClick={handleLoadMore}
            disabled={loading}
            data-testid="load-more"
          >
            {loading ? "Loading..." : "Load more"}
          </button>
        </div>
      )}
    </div>
  );
}
