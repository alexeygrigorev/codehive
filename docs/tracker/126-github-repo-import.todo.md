# Issue #126: Import project from GitHub repos

## Problem

When creating a project from a repository, the user has to manually type a repo URL. Instead, we should pull the user's repos from GitHub and let them pick one.

## Requirements

- [ ] List the user's GitHub repositories for selection
- [ ] Search/filter repos by name
- [ ] Show repo metadata (description, language, last updated, public/private)
- [ ] Clone selected repo to the project directory
- [ ] Auto-create the project from the cloned directory

## Research Required (PM must do during grooming)

- [ ] What's the best way to authenticate with GitHub?
  - Option A: `gh` CLI (user already has it configured) — `gh repo list --json name,url,...`
  - Option B: GitHub API with personal access token (CODEHIVE_GITHUB_TOKEN)
  - Option C: Both — prefer `gh` CLI if installed, fall back to token
  - Think about what makes more sense from user's perspective
- [ ] Should we also support GitLab, Bitbucket, or just GitHub for now?
- [ ] How to handle orgs — show personal repos + org repos?
- [ ] Where to clone to? Default `~/codehive/{repo-name}`?
- [ ] How does this relate to #125 (project directory picker)?

## UX Flow (rough)

1. User clicks "New Project" → "From Repository"
2. App detects GitHub access (gh CLI or token)
3. Shows list of user's repos with search
4. User picks a repo
5. Clone destination pre-filled (`~/codehive/{repo-name}`)
6. Click "Clone & Create"
7. Backend clones repo, creates project pointing to the cloned directory

## Notes

- The "From Repository" card already exists on the New Project page but doesn't work (#124)
- This issue makes it actually functional with GitHub integration
- `gh` CLI approach is simpler (no token management) but requires `gh` to be installed
