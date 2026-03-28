# 157 — Tool call UI: show details, parameters, expandable results

## Problem
When the agent makes tool calls during a session, the UI doesn't show what's happening. The user can't see which tool was called, what parameters were used, or what the result was. It's unclear what the agent is doing.

## Expected behavior
Tool calls should be rendered as distinct UI elements in the chat:

1. **Tool call header**: show tool name (e.g., "read_issue", "write_issue_log", "create_task") with an icon/badge
2. **Parameters**: show the parameters passed to the tool (e.g., `issue_id: "abc-123"`, `file_path: "/src/app.py"`)
3. **Result**: expandable/collapsible section — collapsed by default, click to expand and see the full result
4. **Status**: show if the tool call is in progress (spinner), succeeded, or failed

## What this looks like
```
🔧 read_issue
   issue_id: "abc-123"
   ▶ Result (click to expand)
     ┌──────────────────────
     │ { "title": "Fix sidebar", "status": "open", ... }
     └──────────────────────
```

## Acceptance criteria
- [ ] Tool calls rendered as distinct cards in the chat stream
- [ ] Tool name displayed prominently with icon
- [ ] Parameters shown (key: value format)
- [ ] Result is collapsible — collapsed by default
- [ ] In-progress tool calls show a spinner
- [ ] Failed tool calls show error styling
- [ ] Works for all tool types (read_issue, write_issue_log, create_task, etc.)
- [ ] Dark theme support
