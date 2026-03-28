# 152 — Git init checkbox UX when selecting a directory with existing git repo

## Problem
When creating a new project and selecting a directory that already has a `.git` folder, the "Initialize git repository" checkbox is still shown (unchecked, with "(already a git repo)" hint). This is confusing — if it's already a git repo, the checkbox shouldn't be there at all.

## Current behavior
1. User browses directories, clicks one with a "git" badge
2. Checkbox unchecks and shows "(already a git repo)" text next to it
3. User can still re-check it (which would try to `git init` on an existing repo — no-op but confusing)

## Expected behavior
When the selected directory already has git:
- Hide the checkbox entirely (or show a read-only "Git repository detected" indicator instead)
- Show a small green badge or icon confirming git is present
- If the user manually types a path (not selected from browser), we might not know if it has git — in that case, show the checkbox normally

## UX considerations for the PM to think about
- What happens when the user types a path manually? Should we check for git on the backend?
- Should we show repo info (branch, remote URL) when git is detected?
- Should the "git" badge in the directory browser be more prominent?

## Acceptance criteria
- [ ] When selecting a directory with git from the browser, don't show the init checkbox
- [ ] Show a visual indicator that git is already present (badge, icon, or text)
- [ ] When typing a path manually, keep the checkbox (we don't know if git exists)
- [ ] No regression: creating a project in a non-git directory still shows the checkbox
