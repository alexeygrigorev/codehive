# 19: Web Diff Viewer Component

## Description
Build a diff viewer component for the web app that displays file-level unified diffs. Shows pending vs. applied changes, line-level additions/deletions, and integrates with the changed files panel in the session sidebar.

## Scope
- `web/src/components/DiffViewer.tsx` -- Unified diff display component (line-by-line with syntax highlighting)
- `web/src/components/DiffFileList.tsx` -- File list with diff summary (lines added/removed per file)
- `web/src/components/DiffModal.tsx` -- Full-screen diff modal for detailed review
- `web/src/api/diffs.ts` -- API hooks for fetching session diffs

## Dependencies
- Depends on: #14 (React app scaffolding)
- Depends on: #08 (execution layer diff computation)
