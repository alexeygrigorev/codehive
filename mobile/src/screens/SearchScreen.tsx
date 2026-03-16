import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  TextInput,
  FlatList,
  ActivityIndicator,
  TouchableOpacity,
  StyleSheet,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { SearchStackParamList } from "../navigation/types";
import { searchAll, type SearchResult } from "../api/search";
import SearchResultCard from "../components/SearchResultCard";

type Props = NativeStackScreenProps<SearchStackParamList, "SearchHome">;

type FilterType = "all" | "session" | "message" | "issue" | "event";

const FILTER_OPTIONS: FilterType[] = [
  "all",
  "session",
  "message",
  "issue",
  "event",
];

const DEBOUNCE_MS = 300;
const DEFAULT_LIMIT = 20;

export default function SearchScreen({ navigation }: Props) {
  const [query, setQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<FilterType>("all");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const performSearch = useCallback(
    async (q: string, filter: FilterType) => {
      if (!q.trim()) {
        setResults([]);
        setHasSearched(false);
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const typeFilter = filter === "all" ? undefined : filter;
        const response = await searchAll(q, {
          type: typeFilter,
          limit: DEFAULT_LIMIT,
        });
        setResults(response.results);
        setHasSearched(true);
      } catch {
        setResults([]);
        setHasSearched(true);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    timerRef.current = setTimeout(() => {
      performSearch(query, activeFilter);
    }, DEBOUNCE_MS);
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [query, activeFilter, performSearch]);

  const handleResultPress = useCallback(
    (result: SearchResult) => {
      if (
        result.type === "session" ||
        result.type === "message" ||
        result.type === "event"
      ) {
        const sessionId = result.session_id || result.id;
        navigation.navigate("SessionDetail", { sessionId });
      } else if (result.type === "issue") {
        if (result.project_id) {
          navigation.navigate("ProjectIssues", {
            projectId: result.project_id,
            projectName: result.project_name || "Project",
          });
        }
      }
    },
    [navigation],
  );

  const handleFilterPress = useCallback((filter: FilterType) => {
    setActiveFilter(filter);
  }, []);

  return (
    <View style={styles.container}>
      <TextInput
        style={styles.searchInput}
        placeholder="Search..."
        value={query}
        onChangeText={setQuery}
        autoCapitalize="none"
        autoCorrect={false}
        testID="search-input"
      />
      <View style={styles.filterRow}>
        {FILTER_OPTIONS.map((filter) => (
          <TouchableOpacity
            key={filter}
            style={[
              styles.filterChip,
              activeFilter === filter && styles.filterChipActive,
            ]}
            onPress={() => handleFilterPress(filter)}
            testID={`filter-chip-${filter}`}
          >
            <Text
              style={[
                styles.filterChipText,
                activeFilter === filter && styles.filterChipTextActive,
              ]}
            >
              {filter === "all"
                ? "All"
                : filter.charAt(0).toUpperCase() + filter.slice(1) + "s"}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" testID="loading-spinner" />
        </View>
      ) : !query.trim() ? (
        <View style={styles.center}>
          <Text style={styles.emptyText} testID="empty-state">
            Enter a query to search
          </Text>
        </View>
      ) : hasSearched && results.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emptyText} testID="no-results">
            No results found
          </Text>
        </View>
      ) : (
        <FlatList
          data={results}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <SearchResultCard
              result={item}
              onPress={() => handleResultPress(item)}
            />
          )}
          contentContainerStyle={styles.list}
          testID="search-results-list"
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#f5f5f5",
  },
  searchInput: {
    backgroundColor: "#fff",
    margin: 16,
    marginBottom: 8,
    padding: 12,
    borderRadius: 8,
    fontSize: 16,
    borderWidth: 1,
    borderColor: "#ddd",
  },
  filterRow: {
    flexDirection: "row",
    paddingHorizontal: 16,
    marginBottom: 8,
  },
  filterChip: {
    backgroundColor: "#e0e0e0",
    borderRadius: 16,
    paddingHorizontal: 12,
    paddingVertical: 6,
    marginRight: 8,
  },
  filterChipActive: {
    backgroundColor: "#1565C0",
  },
  filterChipText: {
    fontSize: 13,
    color: "#333",
  },
  filterChipTextActive: {
    color: "#fff",
  },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  emptyText: {
    fontSize: 16,
    color: "#999",
  },
  list: {
    paddingVertical: 8,
  },
});
