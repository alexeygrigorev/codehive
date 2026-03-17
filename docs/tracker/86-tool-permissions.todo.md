# Issue #86: Tool permissions and confirmation in codehive code TUI

## Problem

The `codehive code` TUI runs shell commands, edits files, and makes git commits without asking the user for permission. The NativeEngine has an approval system but it requires the backend API (DB + approval routes). The standalone `codehive code` session bypasses this entirely.

## Requirements

- [ ] Before executing destructive tools (run_shell, edit_file, git_commit), show the action in the TUI and ask the user to approve (y/n/always)
- [ ] "Always" option disables confirmation for that tool type for the rest of the session
- [ ] Read-only tools (read_file, search_files) should not require confirmation
- [ ] Show the full command/edit before asking (not just the tool name)
- [ ] Configurable: `--auto-approve` flag to skip all confirmations
- [ ] The approval should work without DB — purely in-memory in the TUI
