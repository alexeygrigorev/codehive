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

## Log

### [SWE] 2026-03-16 12:00
- Implemented codebase analyzer with four detection strategies: tech stack, frameworks, architecture, conventions
- Tech stack detection supports: pyproject.toml, requirements.txt, package.json, Cargo.toml, go.mod, Gemfile, pom.xml, build.gradle
- Framework detection identifies: FastAPI, Django, Flask, Starlette, Tornado, Sanic, React, Vue, Angular, Next.js, Nuxt, Svelte (from deps and config files)
- Architecture detection: directory layout, monorepo, Docker, CI/CD (GitHub Actions, GitLab CI, Jenkins, CircleCI)
- Conventions detection: linters (ESLint, Ruff, flake8, Pylint, rustfmt), formatters (Prettier, Black), AI instruction files (CLAUDE.md, AGENTS.md, .cursorrules), README presence
- Knowledge writer uses update_knowledge() for merge semantics -- manually-set entries are preserved
- Added POST /api/projects/{id}/knowledge/auto-populate endpoint that returns both analysis results and updated knowledge
- Files created: backend/codehive/core/knowledge_analyzer.py, backend/tests/test_knowledge_analyzer.py
- Files modified: backend/codehive/api/routes/knowledge.py
- Tests added: 31 tests (8 tech stack, 6 framework, 4 architecture, 4 conventions, 4 knowledge merge, 5 API integration)
- Build results: 31 tests pass, 0 fail, ruff clean, format clean
- Known limitations: parsers are lightweight (no toml/yaml libraries) -- handles common formats but may miss edge cases in complex manifests

### [QA] 2026-03-16 13:45
- Tests: 31 passed, 0 failed (test_knowledge_analyzer.py)
- Full suite: 1123 passed, 0 failed
- Ruff check: clean
- Ruff format: clean
- Acceptance criteria:
  - [x] `knowledge_analyzer.py` exists and detects tech stack from pyproject.toml, package.json, Cargo.toml, go.mod: PASS
  - [x] Framework detection identifies FastAPI, Django, React, Vue, Next.js from dependencies: PASS
  - [x] Architecture detection identifies monorepo, docker usage, CI/CD presence: PASS
  - [x] Conventions detection finds linter/formatter configs: PASS
  - [x] POST /api/projects/{id}/knowledge/auto-populate triggers analysis and returns results: PASS
  - [x] Analysis results are merged into existing knowledge (not replaced): PASS
  - [x] Manually-set knowledge entries are preserved: PASS
  - [x] uv run pytest tests/test_knowledge_analyzer.py -v passes with 8+ tests: PASS (31 tests)
- VERDICT: PASS

### [PM] 2026-03-16 14:30
- Reviewed diff: 3 files changed (1 new module, 1 new test file, 1 modified route file)
  - `backend/codehive/core/knowledge_analyzer.py` (466 lines): 4 detection strategies, 2 public functions
  - `backend/tests/test_knowledge_analyzer.py` (451 lines): 31 tests across 5 test classes
  - `backend/codehive/api/routes/knowledge.py`: new POST endpoint added cleanly
- Results verified: real data present -- ran `uv run pytest tests/test_knowledge_analyzer.py -v` and confirmed 31/31 pass in 1.39s
- Acceptance criteria: all 8 met
  - [x] knowledge_analyzer.py exists, detects tech stack from pyproject.toml, package.json, Cargo.toml, go.mod (also requirements.txt, Gemfile, pom.xml, build.gradle)
  - [x] Framework detection: FastAPI, Django, React, Vue, Next.js all covered (plus Flask, Starlette, Tornado, Sanic, Angular, Nuxt, Svelte)
  - [x] Architecture detection: monorepo, docker, CI/CD (GitHub Actions, GitLab CI, Jenkins, CircleCI)
  - [x] Conventions detection: linter/formatter configs, AI instruction files, README
  - [x] POST /api/projects/{id}/knowledge/auto-populate endpoint works, returns {analysis, knowledge}
  - [x] Merge semantics via update_knowledge() -- tested with existing manual entries preserved
  - [x] Manually-set knowledge entries preserved -- test_existing_manual_knowledge_preserved confirms custom_notes survive
  - [x] 31 tests pass (well above the 8+ threshold)
- Code quality notes:
  - Clean separation of concerns: parsers, detection strategies, public API, endpoint
  - Lightweight parsing (no toml/yaml deps) is a reasonable tradeoff noted by SWE
  - Tests use tmp_path fixtures for isolated filesystem testing -- solid pattern
  - API integration tests verify full round-trip (create project, auto-populate, GET knowledge)
  - Error handling covers: missing path (400), nonexistent project (404), empty analysis (no-op)
- No descoped criteria. All spec requirements implemented.
- Follow-up issues created: none needed
- VERDICT: ACCEPT
