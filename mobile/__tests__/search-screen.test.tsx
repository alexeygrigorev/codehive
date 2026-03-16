import React from "react";
import {
  render,
  screen,
  waitFor,
  fireEvent,
  act,
} from "@testing-library/react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import type { SearchStackParamList } from "../src/navigation/types";
import SearchScreen from "../src/screens/SearchScreen";
import { searchAll } from "../src/api/search";

jest.mock("../src/api/search");
const mockSearchAll = searchAll as jest.MockedFunction<typeof searchAll>;

const Stack = createNativeStackNavigator<SearchStackParamList>();

function renderWithNavigation() {
  const Placeholder = () => null;
  return render(
    <NavigationContainer>
      <Stack.Navigator>
        <Stack.Screen name="SearchHome" component={SearchScreen} />
        <Stack.Screen name="SessionDetail" component={Placeholder} />
        <Stack.Screen name="ProjectIssues" component={Placeholder} />
      </Stack.Navigator>
    </NavigationContainer>,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

describe("SearchScreen", () => {
  it("renders search input and filter chips", () => {
    renderWithNavigation();

    expect(screen.getByTestId("search-input")).toBeTruthy();
    expect(screen.getByTestId("filter-chip-all")).toBeTruthy();
    expect(screen.getByTestId("filter-chip-session")).toBeTruthy();
    expect(screen.getByTestId("filter-chip-message")).toBeTruthy();
    expect(screen.getByTestId("filter-chip-issue")).toBeTruthy();
    expect(screen.getByTestId("filter-chip-event")).toBeTruthy();
  });

  it("shows empty state when query is empty", () => {
    renderWithNavigation();

    expect(screen.getByTestId("empty-state")).toBeTruthy();
    expect(screen.getByText("Enter a query to search")).toBeTruthy();
  });

  it("shows no results when API returns empty results array", async () => {
    mockSearchAll.mockResolvedValue({
      results: [],
      total: 0,
      has_more: false,
    });

    renderWithNavigation();

    fireEvent.changeText(screen.getByTestId("search-input"), "nonexistent");

    // Advance past debounce
    await act(async () => {
      jest.advanceTimersByTime(400);
    });

    await waitFor(() => {
      expect(screen.getByTestId("no-results")).toBeTruthy();
      expect(screen.getByText("No results found")).toBeTruthy();
    });
  });

  it("shows loading indicator while request is pending", async () => {
    // Never resolve so we stay in loading state
    mockSearchAll.mockReturnValue(new Promise(() => {}));

    renderWithNavigation();

    fireEvent.changeText(screen.getByTestId("search-input"), "test");

    await act(async () => {
      jest.advanceTimersByTime(400);
    });

    await waitFor(() => {
      expect(screen.getByTestId("loading-spinner")).toBeTruthy();
    });
  });

  it("renders result cards when API returns results", async () => {
    mockSearchAll.mockResolvedValue({
      results: [
        {
          type: "session",
          id: "s1",
          snippet: "Found session",
          score: 0.9,
          created_at: new Date().toISOString(),
          project_name: "Test Project",
        },
      ],
      total: 1,
      has_more: false,
    });

    renderWithNavigation();

    fireEvent.changeText(screen.getByTestId("search-input"), "found");

    await act(async () => {
      jest.advanceTimersByTime(400);
    });

    await waitFor(() => {
      expect(screen.getByText("Found session")).toBeTruthy();
      expect(screen.getByText("session")).toBeTruthy();
    });
  });

  it("selecting a type filter chip updates the active filter", async () => {
    mockSearchAll.mockResolvedValue({
      results: [],
      total: 0,
      has_more: false,
    });

    renderWithNavigation();

    // Type a query first so the filter triggers a search
    fireEvent.changeText(screen.getByTestId("search-input"), "test");

    await act(async () => {
      jest.advanceTimersByTime(400);
    });

    await waitFor(() => {
      expect(mockSearchAll).toHaveBeenCalledWith("test", {
        type: undefined,
        limit: 20,
      });
    });

    mockSearchAll.mockClear();

    // Now tap the "session" filter chip
    fireEvent.press(screen.getByTestId("filter-chip-session"));

    await act(async () => {
      jest.advanceTimersByTime(400);
    });

    await waitFor(() => {
      expect(mockSearchAll).toHaveBeenCalledWith("test", {
        type: "session",
        limit: 20,
      });
    });
  });
});
