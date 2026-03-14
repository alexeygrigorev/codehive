# 35: GitHub Issue Import (One-Way Sync)

## Description
Implement one-way import of GitHub Issues into codehive's internal issue tracker. Support manual import and periodic sync as a fallback. Map GitHub labels and status to internal issue fields.

## Scope
- `backend/codehive/integrations/github/client.py` -- GitHub API client (using PyGithub or httpx) for fetching issues
- `backend/codehive/integrations/github/importer.py` -- Issue import logic: fetch GitHub issues, map fields, create/update internal issues
- `backend/codehive/integrations/github/mapper.py` -- Map GitHub labels/status/assignees to internal issue fields
- `backend/codehive/api/routes/github.py` -- Endpoints: configure GitHub token per project, trigger manual import, list sync status
- `backend/codehive/config.py` -- Add GitHub token setting
- `backend/tests/test_github_import.py` -- Import and mapping tests

## Dependencies
- Depends on: #46 (issue tracker API for internal issues)
- Depends on: #04 (project CRUD)
