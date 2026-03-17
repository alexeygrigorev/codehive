# Issue #87: Dangerous command guardrails

## Problem

The agent can execute arbitrary shell commands via `run_shell`. Some commands are destructive and hard to reverse. Need a guardrail layer that blocks or requires explicit confirmation for dangerous commands, independent of the general tool permission system (#86).

## Dangerous commands to guard against

### Git — destructive/irreversible
- `git push --force` / `git push -f` — overwrites remote history
- `git push --force-with-lease` — less dangerous but still destructive
- `git reset --hard` — discards uncommitted changes
- `git clean -f` / `git clean -fd` — deletes untracked files
- `git checkout -- .` / `git restore .` — discards all working tree changes
- `git branch -D` — force-deletes a branch
- `git rebase` (on shared branches) — rewrites history
- `git stash drop` / `git stash clear` — permanently loses stashed work

### File system — destructive
- `rm -rf` / `rm -r` — recursive delete
- `rm` on files outside project root
- `rmdir` — directory removal
- `mv` / `cp` overwriting existing files outside project
- `chmod` / `chown` — permission changes
- `shred` — secure delete

### System — dangerous
- `kill` / `killall` / `pkill` — process termination
- `shutdown` / `reboot` / `halt`
- `mkfs` / `fdisk` / `dd` — disk operations
- `iptables` / `ufw` — firewall changes
- `systemctl stop/disable` — service management
- `apt remove` / `pip uninstall` / `npm uninstall -g` — package removal

### Data — destructive
- `DROP TABLE` / `DROP DATABASE` / `TRUNCATE` (via psql, sqlite3, etc.)
- `docker rm` / `docker rmi` / `docker system prune`
- `docker compose down -v` — removes volumes with data

### Network — risky
- `curl -X DELETE` / `curl -X PUT` to external APIs
- `wget` / `curl` piped to `sh` or `bash`
- `ssh` / `scp` to remote hosts

### Secrets — leaking
- `echo $SECRET` / `env` / `printenv` — may expose secrets
- `cat .env` / `cat credentials` — reading secret files
- Any command that might output API keys, tokens, passwords

## Requirements

- [ ] Define a `CommandPolicy` with ALLOW / DENY / ASK verdicts (already exists in `execution/policy.py`)
- [ ] Create a default dangerous commands list with regex patterns
- [ ] DENY by default: commands that are almost never what you want (rm -rf /, shutdown, mkfs, dd)
- [ ] ASK by default: commands that are sometimes valid but dangerous (git push --force, rm -rf on project dirs, docker rm)
- [ ] ALLOW by default: safe commands (git status, ls, cat, grep, python, npm test, etc.)
- [ ] Wire the policy into `run_shell` execution in NativeEngine
- [ ] In `codehive code` TUI: show the blocked command and reason, let user override with explicit confirmation
- [ ] Log all denied/overridden commands
- [ ] `--no-guardrails` flag to disable (for advanced users who know what they're doing)

## Notes

- The existing `CommandPolicy` in `execution/policy.py` already has the ALLOW/DENY/ASK verdict pattern — extend it with a default dangerous commands ruleset
- This is complementary to #86 (tool permissions) — #86 is about confirming all tool use, this is specifically about catching dangerous shell commands
- The agent should receive a clear error message when a command is denied so it can choose a safer alternative
