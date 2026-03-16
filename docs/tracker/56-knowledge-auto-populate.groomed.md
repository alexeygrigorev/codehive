# 56: Knowledge Base Auto-Population

## Description
Analyze a project's codebase to auto-detect and populate the knowledge base: tech stack, architecture, conventions, dependencies. Currently knowledge is manual CRUD only. This is a single issue (no split needed).

## Implementation Plan

### 1. Codebase analyzer
- `backend/codehive/core/knowledge_analyzer.py`
- `async def analyze_codebase(project_path: str) -> dict` -- scans the project directory and returns structured knowledge

### 2. Detection strategies
Each strategy scans specific files and returns knowledge fragments:

- **Tech stack detection**:
  - `pyproject.toml` / `requirements.txt` -> Python + dependencies
  - `package.json` -> Node.js/TypeScript + dependencies
  - `Cargo.toml` -> Rust + dependencies
  - `go.mod` -> Go + dependencies
  - `Gemfile` -> Ruby + dependencies
  - `pom.xml` / `build.gradle` -> Java/Kotlin + dependencies

- **Framework detection**:
  - Look for `fastapi`, `django`, `flask` in Python deps
  - Look for `react`, `vue`, `angular`, `next` in JS deps
  - Look for framework-specific config files (`next.config.js`, `vite.config.ts`, etc.)

- **Architecture detection**:
  - Scan directory structure for patterns: `src/`, `tests/`, `docs/`, `api/`, `core/`, `models/`
  - Detect monorepo (multiple `pyproject.toml`/`package.json` files)
  - Detect docker usage (`Dockerfile`, `docker-compose.yml`)
  - Detect CI/CD (`.github/workflows/`, `.gitlab-ci.yml`)

- **Conventions detection**:
  - Check for linter configs (`.eslintrc`, `ruff.toml`, `.flake8`)
  - Check for formatter configs (`prettier`, `black`, `rustfmt`)
  - Check for `CLAUDE.md`, `AGENTS.md`, `.cursorrules`
  - Read existing README for project description

### 3. Knowledge writer
- `async def populate_knowledge(db, project_id, analysis_result)` -- writes the analysis into the project's knowledge JSONB field
- Uses `update_knowledge()` from existing `core/knowledge.py`
- Knowledge keys: `tech_stack`, `frameworks`, `architecture`, `conventions`, `dependencies`, `detected_at`
- Does NOT overwrite manually-set knowledge entries (merge, not replace)

### 4. API endpoint
- `POST /api/projects/{project_id}/knowledge/auto-populate` -- triggers analysis
- Returns the detected knowledge
- Add to `backend/codehive/api/routes/knowledge.py`

### 5. Trigger points
- Can be called manually via API
- Called automatically during "Start from repo" project flow (#55a)
- Could be called on project creation when path is set

## Acceptance Criteria

- [ ] `knowledge_analyzer.py` exists and detects tech stack from `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`
- [ ] Framework detection identifies FastAPI, Django, React, Vue, Next.js from dependencies
- [ ] Architecture detection identifies monorepo, docker usage, CI/CD presence
- [ ] Conventions detection finds linter/formatter configs
- [ ] `POST /api/projects/{id}/knowledge/auto-populate` triggers analysis and returns results
- [ ] Analysis results are merged into existing knowledge (not replaced)
- [ ] Manually-set knowledge entries are preserved
- [ ] `uv run pytest tests/test_knowledge_analyzer.py -v` passes with 8+ tests

## Test Scenarios

### Unit: Tech stack detection
- Project with `pyproject.toml` containing FastAPI -> detects Python + FastAPI
- Project with `package.json` containing React -> detects Node.js + React
- Project with `Cargo.toml` -> detects Rust
- Project with no recognized files -> returns empty tech stack

### Unit: Architecture detection
- Directory with `src/`, `tests/`, `docs/` -> detects standard layout
- Directory with `Dockerfile` + `docker-compose.yml` -> detects Docker usage
- Directory with `.github/workflows/` -> detects GitHub Actions CI

### Unit: Knowledge merge
- Existing knowledge has `custom_notes: "keep me"`, auto-populate runs, verify `custom_notes` preserved
- Auto-populate runs twice, verify no duplicate entries

### Integration: API endpoint
- Create project, call auto-populate endpoint, verify knowledge is populated
- Verify response contains detected tech stack and frameworks

## Dependencies
- Depends on: #48 (knowledge base CRUD), #08 (execution layer for file reading)
