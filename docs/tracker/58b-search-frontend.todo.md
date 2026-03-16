# 58b: Search Frontend UI

## Description
Web UI for searching across codehive: search bar in the header, results page with filtering, and search-as-you-type with debouncing.

## Implementation Plan

### 1. Search bar
- `web/src/components/SearchBar.tsx` -- input field in the app header/navbar
- Debounced input (300ms) triggers search API call
- Shows dropdown with quick results (top 5)
- Pressing Enter or clicking "See all" navigates to full results page

### 2. Search results page
- `web/src/pages/SearchPage.tsx` -- route: `/search?q={query}`
- Tabbed results: All, Sessions, Messages, Issues, Events
- Each result shows: type icon, title/snippet with highlighted terms, project name, timestamp
- Clicking a result navigates to the relevant entity (session, issue, etc.)
- Pagination: "Load more" or infinite scroll

### 3. Result components
- `web/src/components/search/SearchResult.tsx` -- generic result card
- `web/src/components/search/SearchFilters.tsx` -- sidebar filters (type, project, date range)
- `web/src/components/search/SearchHighlight.tsx` -- highlights matched terms in snippets

### 4. Session history search
- Add search input to the session detail page (within the chat panel)
- Searches within the current session's messages
- Highlights and scrolls to matched messages

### 5. API integration
- `web/src/api/search.ts` -- `searchAll(query, filters)`, `searchSessionHistory(sessionId, query)`
- Uses the endpoints from #58a

## Acceptance Criteria

- [ ] Search bar appears in the app header on all pages
- [ ] Typing in the search bar shows a dropdown with top 5 results (debounced)
- [ ] Pressing Enter navigates to `/search?q={query}`
- [ ] Search results page shows results grouped by type (tabs)
- [ ] Each result shows type icon, snippet with highlighted terms, project, timestamp
- [ ] Clicking a result navigates to the correct entity
- [ ] Type filter works: clicking "Sessions" tab shows only session results
- [ ] Session detail page has a search input for within-session search
- [ ] Empty state shown when no results found

## Test Scenarios

### Unit: SearchBar
- Render SearchBar, type text, verify debounced API call after 300ms
- Verify dropdown renders with mock results
- Press Enter, verify navigation to SearchPage

### Unit: SearchResult
- Render with session result, verify session icon and link
- Render with message result, verify snippet is highlighted
- Click result, verify navigation to correct URL

### Unit: SearchPage
- Render with query param, verify API call with correct query
- Switch tabs, verify filter is applied
- Verify pagination loads more results

### Integration: End-to-end
- Type "auth" in search bar, verify dropdown shows results
- Navigate to search page, verify full results with filters
- Click a result, verify navigation to the entity

## Dependencies
- Depends on: #58a (search backend API), #14 (React app)
