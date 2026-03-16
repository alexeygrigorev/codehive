# 82: Database Backup Automation

## Description

Add a simple pg_dump-based backup script for the single-user self-hosted instance. This is personal data protection, not enterprise DR. The script dumps the PostgreSQL database to a local directory, supports a configurable retention window (e.g., keep last 7 daily backups), and can be triggered manually or via cron. Include clear restore instructions so the user can recover their workspace, projects, sessions, and agent history from a backup file.

## Dependencies

- Depends on: #02 (docker-compose) -- DONE
- Depends on: #57 (deployment-docker) -- should be groomed/done first for Dockerfile context

## Scope

### In scope
- A `codehive backup` CLI command that runs `pg_dump` and saves a compressed dump file
- A `codehive backup restore <file>` CLI command that restores from a dump file
- A `codehive backup list` CLI command that lists available backups with timestamps and sizes
- Configurable backup directory via `CODEHIVE_BACKUP_DIR` (default: `./backups`)
- Configurable retention count via `CODEHIVE_BACKUP_RETENTION` (default: 7)
- Automatic pruning of old backups beyond the retention count after each new backup
- A standalone shell script (`scripts/backup.sh`) suitable for cron scheduling
- Restore documentation in the script output and in a section of the issue

### Out of scope
- Remote/cloud backup destinations (S3, etc.)
- Incremental or WAL-based backups
- Automated scheduling (user sets up cron themselves)
- Redis backup (session data in Redis is ephemeral)
- Multi-database or multi-tenant support

## Acceptance Criteria

- [ ] `uv run codehive backup` creates a gzipped pg_dump file in the configured backup directory
- [ ] Backup filename includes a timestamp (e.g., `codehive-2026-03-16T10-30-00.sql.gz`)
- [ ] `uv run codehive backup list` prints available backup files sorted by date, showing filename, size, and age
- [ ] `uv run codehive backup restore <file>` restores the database from the specified dump file
- [ ] After backup, files exceeding the retention count are automatically deleted (oldest first)
- [ ] `CODEHIVE_BACKUP_DIR` and `CODEHIVE_BACKUP_RETENTION` settings exist in `config.py` with defaults
- [ ] `scripts/backup.sh` exists, is executable, and can be added to crontab (includes example crontab line in a comment)
- [ ] Backup works against both local PostgreSQL and the dockerized PostgreSQL (via `DATABASE_URL`)
- [ ] Restore prints a clear warning that it will overwrite the current database and requires confirmation (unless `--yes` flag is passed)
- [ ] `uv run pytest tests/test_backup.py -v` passes with 5+ tests
- [ ] CLI help (`codehive backup --help`) documents all subcommands

## Test Scenarios

### Unit: Backup file management
- Create a backup file, verify it exists in the backup directory with correct naming pattern
- Create 10 backup files, run pruning with retention=7, verify only 7 newest remain
- Verify pruning does not delete files that are not codehive backup files (no accidental deletion of unrelated files)
- Verify backup directory is created automatically if it does not exist
- Verify backup fails gracefully with a clear error when pg_dump is not available or database is unreachable

### Unit: Configuration
- Verify default backup directory is `./backups`
- Verify default retention count is 7
- Verify settings are overridable via `CODEHIVE_BACKUP_DIR` and `CODEHIVE_BACKUP_RETENTION` environment variables

### Integration: CLI commands
- `codehive backup` creates a dump file and prints the file path to stdout
- `codehive backup list` with no backups prints an informative message
- `codehive backup list` with existing backups shows correct count, sizes, and sorted order
- `codehive backup restore` with `--yes` flag skips confirmation prompt

### Integration: Backup and restore round-trip (requires running PostgreSQL)
- Create test data in the database, run backup, drop data, restore from backup, verify data is present again

## Implementation Notes

- Use `pg_dump --format=custom` or `pg_dump | gzip` for compressed output. Custom format is preferred as it allows `pg_restore` with selective restore options.
- Parse `DATABASE_URL` from settings to extract host, port, user, password, dbname for pg_dump/pg_restore invocation. Alternatively, use `PGPASSWORD` env var.
- The CLI subcommands should follow the existing argparse pattern in `cli.py`.
- The backup script (`scripts/backup.sh`) should source `.env` or accept `DATABASE_URL` as an environment variable.
- Retention pruning should sort by filename timestamp (not filesystem mtime) for deterministic behavior.

## Log

### [SWE] 2026-03-16 12:00
- Implemented database backup automation with pg_dump/psql-based backup and restore
- Created `backend/codehive/core/backup.py` with functions: parse_database_url, create_backup, list_backups, prune_backups, restore_backup, format_size, format_age
- Added `backup_dir` and `backup_retention` settings to `backend/codehive/config.py` (defaults: `./backups`, 7)
- Added `backup` CLI subcommand group to `backend/codehive/cli.py` with create/list/restore actions
- Created `scripts/backup.sh` cron-friendly wrapper script (executable, sources .env, includes crontab example)
- Backup creates gzipped SQL dumps with timestamp filenames (e.g., `codehive-2026-03-16T10-30-00.sql.gz`)
- Restore requires confirmation prompt unless `--yes` flag is passed
- Running `codehive backup` without subcommand defaults to `create`
- Auto-prunes old backups after each create, keeping newest N per retention setting
- Files modified: backend/codehive/core/backup.py (new), backend/codehive/config.py, backend/codehive/cli.py, scripts/backup.sh (new), backend/tests/test_backup.py (new)
- Tests added: 38 tests covering URL parsing, config defaults/overrides, backup creation (mocked), listing, pruning, restore (mocked), CLI commands, and formatting helpers
- Build results: 38 tests pass, 0 fail, ruff clean

### [QA] 2026-03-16 16:00
- Tests: 38 passed, 0 failed (test_backup.py); full suite 1477 passed, 3 skipped
- Ruff: clean (all changed files)
- Format: clean (all changed files)
- Acceptance criteria:
  1. `codehive backup` creates gzipped pg_dump file: PASS
  2. Backup filename includes timestamp: PASS
  3. `codehive backup list` shows filename, size, age sorted by date: PASS
  4. `codehive backup restore <file>` restores from dump: PASS
  5. Auto-pruning after backup (oldest first): PASS
  6. `CODEHIVE_BACKUP_DIR` and `CODEHIVE_BACKUP_RETENTION` in config with defaults: PASS
  7. `scripts/backup.sh` exists, executable, crontab example: PASS
  8. Works with any PostgreSQL via DATABASE_URL: PASS
  9. Restore warns and requires confirmation (skippable with --yes): PASS
  10. 5+ tests pass: PASS (38 tests)
  11. CLI help documents all subcommands: PASS
- VERDICT: PASS

### [PM] 2026-03-16 16:30
- Reviewed diff: 5 files changed (backup.py new, test_backup.py new, backup.sh new, cli.py modified, config.py modified)
- Results verified: 38/38 tests pass, CLI help confirms all subcommands, backup.sh is executable with crontab example
- Acceptance criteria: all 11 met
  1. `codehive backup` creates gzipped pg_dump file: MET (create_backup with gzip.open, CLI wired, test confirms)
  2. Backup filename includes timestamp: MET (pattern codehive-YYYY-MM-DDTHH-MM-SS.sql.gz, regex enforced)
  3. `codehive backup list` prints sorted backups with filename/size/age: MET (list_backups + format helpers, CLI output verified)
  4. `codehive backup restore <file>` restores via psql: MET (decompresses gzip, pipes to psql, tested with mock)
  5. Auto-pruning after backup: MET (_backup_create calls prune_backups, 4 pruning tests)
  6. Config settings with defaults: MET (backup_dir="./backups", backup_retention=7, env override tests pass)
  7. scripts/backup.sh exists, executable, crontab example: MET (755 permissions, crontab comment, sources .env)
  8. Works via DATABASE_URL: MET (parse_database_url handles postgresql+asyncpg:// and postgresql://)
  9. Restore requires confirmation unless --yes: MET (CLI prompts, --yes skips, tested)
  10. 5+ tests pass: MET (38 tests)
  11. CLI help documents all subcommands: MET (verified: create, list, restore shown)
- Follow-up issues created: none needed
- VERDICT: ACCEPT
