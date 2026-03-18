# Issue #125: Improve project creation — default directory, folder picker, git init

## Problem

Project creation asks for a directory path typed manually. This should be smarter:

1. No default starting point — should default to `~/codehive/` or similar
2. No way to browse/select existing folders — have to type the full path
3. No option to initialize git in the new project directory

## Requirements

- [ ] Default project directory: `~/codehive/` (or configurable base path)
- [ ] Pre-fill the path field with the default directory + project name
- [ ] Folder picker / browser — similar to "Open Folder" in VS Code:
  - Show existing directories under the default path
  - Allow navigating the filesystem
  - Or at minimum: show recent/existing project directories as suggestions
- [ ] "Initialize git repository" checkbox (checked by default)
  - When checked: run `git init` in the project directory after creation
  - Show the checkbox in the creation form
- [ ] Create the directory if it doesn't exist

## UX Flow

1. User clicks "New Project" → "Empty Project"
2. Path field shows `~/codehive/` as prefix
3. User types project name → path becomes `~/codehive/myproject`
4. Below: list of existing folders in `~/codehive/` as quick-select options
5. "Initialize git repository" checkbox (checked by default)
6. Click "Create Project"
7. Backend creates directory (if needed), runs `git init` (if checked), creates project

## UX Research Required (PM must do during grooming)

Think about the full project creation UX from the user's perspective:

- What does a developer expect when they click "New Project"?
- How does VS Code "Open Folder" work? How does Cursor? How does GitHub Desktop? How does OpenCode (desktop version)?
- Should we support "Open Existing Project" as a separate flow from "Create New Project"?
- What about cloning a repo? (`git clone` → auto-create project)
- Should recent projects appear on the dashboard for quick access?
- What happens if the user picks a directory that already has a project? (re-open it vs error)
- Should there be a "workspace root" setting in app preferences?
- How does this interact with the CLI (`codehive code /path/to/dir`)?

The PM should think holistically about the project lifecycle: discover → create/open → work → revisit.

## Notes

- The folder browser could be a simple list from a `GET /api/system/directories?path=...` endpoint
- For security: restrict browsable paths to user's home directory
- Consider: `~/codehive/` as the "workspace" concept (without the old Workspace model)
