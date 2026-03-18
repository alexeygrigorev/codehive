# Issue #101: Fix dark theme — visual issues across the web app

## Problem

The dark theme (#89) was implemented by adding `dark:` Tailwind variants to ~55 component files, but the result has visual problems. Likely issues include: poor contrast, inconsistent backgrounds, elements that still look "light" in dark mode, unreadable text, borders that disappear, inputs/selects with wrong colors, status badges that look off.

## Requirements

- [ ] Audit every page in dark mode and fix visual issues:
  - Dashboard
  - New Project page
  - Project page (sessions + issues tabs, session creation form)
  - Session page (chat, sidebar, activity panel, tool calls)
  - Login/Register pages (if auth enabled)
- [ ] Ensure consistent dark background hierarchy (e.g., bg-gray-900 for page, bg-gray-800 for cards, bg-gray-700 for inputs)
- [ ] Fix text contrast — all text must be readable against dark backgrounds
- [ ] Fix borders — visible but subtle (gray-700 or gray-600, not gray-200)
- [ ] Fix status badges — readable in both themes
- [ ] Fix code blocks / diffs — proper dark mode colors
- [ ] Fix the theme toggle — clear visual indicator of current mode
- [ ] Ensure no white flashes on page load (html element gets dark class before paint)

## Acceptance Criteria

- [ ] Every page looks correct in dark mode — no white backgrounds, no unreadable text, no invisible borders
- [ ] Every page looks correct in light mode — no regressions from the dark theme changes
- [ ] Theme toggle clearly shows current state (sun/moon icon or similar)
- [ ] Screenshots of every page in both themes included in the QA log (use a headless browser or describe what was verified)
- [ ] No `bg-white` without a corresponding `dark:bg-*` anywhere in the codebase
- [ ] No `text-gray-*` without a corresponding `dark:text-gray-*` for body text
- [ ] No `border-gray-200` without a corresponding `dark:border-gray-*`
- [ ] All existing tests pass
- [ ] Ruff/lint clean

## QA Requirements

QA must verify visually — not just run tests. For each page:
1. Switch to dark mode via the toggle
2. Describe what is visible: backgrounds, text, borders, inputs, buttons, badges
3. Note any issues (e.g., "chat input has white background in dark mode")
4. Verify the fix resolves each issue

## Notes

- The SWE should `grep -r "bg-white" web/src/` and `grep -r "border-gray-200" web/src/` to find missing dark variants
- Consider adding a base dark theme in `index.css` or `App.css` so components inherit dark colors by default instead of specifying on every element
- The root `<html>` element should get the `dark` class — check ThemeContext.tsx
