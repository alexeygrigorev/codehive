import "@testing-library/jest-dom/vitest";

// Provide a default matchMedia mock for jsdom (which doesn't implement it)
if (!window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: query.includes("min-width: 1024px"), // default to desktop
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    onchange: null,
    dispatchEvent: () => false,
  });
}
