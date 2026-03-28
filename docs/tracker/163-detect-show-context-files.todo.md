# 163 — Detect and display context files (CLAUDE.md, agent.md, etc.)

## Problem
When a project directory has files like CLAUDE.md, .cursorrules, agent.md, or similar, these get included in the agent's context automatically by the CLI engines. But the user has no visibility into what context files exist or what's being sent to the agent.

## Expected behavior
1. **Detection**: On project creation or when viewing a project, scan the project directory for known context files
2. **Display**: Show detected context files on the project page (e.g., "Context files: CLAUDE.md, .cursorrules")
3. **Preview**: Click on a file to see its contents
4. **Known patterns**: CLAUDE.md, .claude/*, agent.md, .cursorrules, .github/copilot-instructions.md, AGENTS.md, .codex/*, .gemini

## Acceptance criteria
- [ ] Backend endpoint to scan project directory for known context files
- [ ] Project page shows detected context files with their paths
- [ ] Click to preview file contents
- [ ] Handles missing files gracefully (project path doesn't exist, etc.)
- [ ] List of known patterns is configurable/extensible
