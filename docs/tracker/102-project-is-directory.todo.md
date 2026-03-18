# Issue #102: Project creation should ask for directory, not name

## Problem

When creating a project in the web UI ("Empty Project" button), it prompts for a name. But a project IS a directory — the user should specify the path, and the name should be derived from the directory basename.

## Requirements

- [ ] "Empty Project" creation asks for directory path instead of name
- [ ] Name is auto-derived from the directory basename (e.g., `/home/user/git/myapp` → "myapp")
- [ ] User can optionally override the name
- [ ] The project's `path` field is set to the directory
- [ ] Validate that the path looks like an absolute path
- [ ] Session creation form: option to set working directory for the session

## Notes

- This aligns with the CLI behavior: `codehive code /path/to/dir` creates a project from the directory
- The `by-path` API endpoint (#94a) already supports this: POST /api/projects/by-path
