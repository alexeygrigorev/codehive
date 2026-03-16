# 82: Database Backup Automation

## Description
Add a simple pg_dump-based backup script for the single-user self-hosted instance. This is personal data protection, not enterprise DR. The script dumps the PostgreSQL database to a local directory, supports a configurable retention window (e.g., keep last 7 daily backups), and can be triggered manually or via cron. Include clear restore instructions so the user can recover their workspace, projects, sessions, and agent history from a backup file.

## Dependencies
- Depends on: #02 (docker-compose), #57a (Dockerfile)
