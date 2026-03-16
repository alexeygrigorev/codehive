#!/usr/bin/env bash
# Codehive database backup script.
# Suitable for running via cron.
#
# Example crontab entry (daily at 2:00 AM):
#   0 2 * * * /path/to/codehive/scripts/backup.sh >> /var/log/codehive-backup.log 2>&1
#
# Environment variables (set these or source a .env file):
#   CODEHIVE_DATABASE_URL   - PostgreSQL connection URL (required)
#   CODEHIVE_BACKUP_DIR     - Directory to store backups (default: ./backups)
#   CODEHIVE_BACKUP_RETENTION - Number of backups to keep (default: 7)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Source .env if it exists
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/.env"
    set +a
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting codehive backup..."

cd "$PROJECT_DIR/backend"
uv run codehive backup create

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Backup complete."
