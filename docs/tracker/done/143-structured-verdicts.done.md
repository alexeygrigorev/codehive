# 143 — Structured agent verdicts: PASS/FAIL/ACCEPT/REJECT

## Problem

Agents report results as free text. The orchestrator uses regex (`_VERDICT_PATTERNS`) to parse natural language and extract PASS/FAIL/ACCEPT/REJECT from agent output. This is fragile: if an agent phrases its verdict differently, the regex misses it and the orchestrator defaults to FAIL, causing spurious rejection loops. The verdict data (evidence links, per-criterion results) is also lost -- only the raw text blob is stored in the issue log.

## Solution

Replace free-text verdict parsing with structured verdict events. Agents call a `submit_verdict` tool that writes a typed `Event` record with `type="verdict"` to the session's event stream. The orchestrator reads the verdict event programmatically from the DB instead of parsing text. Evidence (screenshot paths, test output excerpts, per-criterion PASS/FAIL) is stored as structured JSON in the event's `data` column.

## Dependencies

- Issue #22 (orchestrator-mode) -- DONE
- Issue #07 (event-bus) -- DONE
- Issue #46 (issue-tracker-api) -- DONE

No blocking dependencies remain. This issue can be picked up immediately.

---

## User Stories

### Story: QA agent submits a structured PASS verdict

1. QA agent finishes running tests for a task
2. QA agent calls `submit_verdict` with `verdict="PASS"`, `evidence=[{"type": "test_output", "content": "12 passed, 0 failed"}]`, and `criteria_results=[{"criterion": "Health endpoint returns 200", "result": "PASS"}]`
3. A new `Event` row is created in the DB with `type="verdict"` and `session_id` matching the QA agent's session
4. The `Event.data` JSON contains `{"verdict": "PASS", "role": "qa", "evidence": [...], "criteria_results": [...]}`
5. The orchestrator queries for the verdict event on the agent's session, reads `data.verdict`, and routes the task to the "accepting" step -- no regex parsing involved

### Story: PM agent submits a structured REJECT verdict with feedback

1. PM agent reviews QA evidence and finds missing acceptance criteria
2. PM agent calls `submit_verdict` with `verdict="REJECT"`, `feedback="Health endpoint missing version field"`, `evidence=[...]`
3. A new `Event` row is created with `type="verdict"` and the PM's session ID
4. The `Event.data` JSON contains `{"verdict": "REJECT", "role": "pm", "feedback": "Health endpoint missing version field", "evidence": [...]}`
5. The orchestrator reads `data.verdict == "REJECT"` and routes the task back to "implementing", passing `data.feedback` as the rejection reason

### Story: Orchestrator handles a session that never submits a verdict

1. An agent session completes without calling `submit_verdict` (e.g., it crashes or times out)
2. The orchestrator queries the agent session's events for `type="verdict"` and finds none
3. The orchestrator falls back to the existing `parse_verdict` regex on the session output text as a degraded-mode fallback
4. If neither structured nor text verdict is found, the orchestrator defaults to FAIL (safe default, unchanged behavior)

---

## Technical Notes

### Verdict event schema

The `Event` model already has `type: str` and `data: JSON` columns. No schema migration is needed. The verdict event uses:

```python
Event(
    session_id=agent_session_id,
    type="verdict",
    data={
        "verdict": "PASS" | "FAIL" | "ACCEPT" | "REJECT",
        "role": "qa" | "pm" | "swe",
        "task_id": "<uuid>",
        "evidence": [
            {"type": "test_output", "content": "..."},
            {"type": "screenshot", "path": "/tmp/screenshot-001.png"},
            {"type": "log_excerpt", "content": "..."},
        ],
        "criteria_results": [
            {"criterion": "Health endpoint returns 200", "result": "PASS"},
            {"criterion": "Version field present", "result": "FAIL", "detail": "missing"},
        ],
        "feedback": "optional free-text feedback (used for REJECT/FAIL)",
    },
)
```

### New module: `backend/codehive/core/verdicts.py`

- `submit_verdict(db, session_id, task_id, verdict, role, evidence=None, criteria_results=None, feedback=None) -> Event` -- validates inputs, creates the Event row, returns it.
- `get_verdict(db, session_id) -> dict | None` -- queries the most recent `type="verdict"` event for the session, returns `event.data` or `None`.
- Pydantic models for request validation: `VerdictPayload`, `EvidenceItem`, `CriterionResult`.

### Changes to `orchestrator_service.py`

- `_run_pipeline_step` currently calls `parse_verdict(output)` on the raw text. After this issue, it first calls `get_verdict(db, child_session_id)`. If a structured verdict exists, use it. If not, fall back to `parse_verdict(output)`.
- `StepResult` gains optional fields: `evidence: list[dict] | None`, `criteria_results: list[dict] | None`, `feedback: str | None`.
- The `build_instructions` function adds a note to agents that they should call `submit_verdict` instead of writing "VERDICT: PASS" in free text.

### Changes to `build_instructions`

- Testing and accepting instructions should tell agents to use the `submit_verdict` tool and include the expected schema.

### No DB migration required

The `Event` table already stores arbitrary JSON in `data`. The new `type="verdict"` is just a new event type value.

---

## Acceptance Criteria

- [ ] A `submit_verdict` function in `backend/codehive/core/verdicts.py` creates an `Event` with `type="verdict"` and structured `data` containing at minimum `verdict`, `role`, and `task_id`
- [ ] A `get_verdict` function in `backend/codehive/core/verdicts.py` retrieves the most recent verdict event for a given session, returning the parsed `data` dict or `None`
- [ ] Pydantic models `VerdictPayload`, `EvidenceItem`, `CriterionResult` validate the verdict schema (verdict must be one of PASS/FAIL/ACCEPT/REJECT; evidence items have type+content or type+path; criterion results have criterion+result)
- [ ] `OrchestratorService._run_pipeline_step` reads the structured verdict first via `get_verdict`, falling back to `parse_verdict` on the raw text only when no verdict event exists
- [ ] `StepResult` includes `evidence`, `criteria_results`, and `feedback` fields populated from the structured verdict when available
- [ ] `build_instructions` for "testing" and "accepting" steps includes guidance telling agents to call `submit_verdict` with the expected schema
- [ ] The existing `parse_verdict` regex function is preserved as a fallback (not deleted) for backward compatibility
- [ ] `cd backend && uv run pytest tests/ -v` passes with all existing tests still green plus 10+ new tests covering the verdict module
- [ ] `cd backend && uv run ruff check` is clean

---

## Test Scenarios

### Unit: `submit_verdict` function

- Call `submit_verdict` with verdict="PASS", role="qa", task_id=<uuid> -- verify an Event row is created with `type="verdict"` and correct `data` JSON
- Call `submit_verdict` with all optional fields (evidence, criteria_results, feedback) -- verify all fields stored in `data`
- Call `submit_verdict` with invalid verdict value (e.g., "MAYBE") -- verify validation error raised
- Call `submit_verdict` with invalid session_id -- verify appropriate error raised

### Unit: `get_verdict` function

- Create a verdict event for a session, call `get_verdict` -- verify returns the `data` dict with correct verdict
- Call `get_verdict` on a session with no verdict events -- verify returns `None`
- Create multiple verdict events for a session (e.g., agent resubmits), call `get_verdict` -- verify returns the most recent one

### Unit: Pydantic models

- `VerdictPayload` with valid PASS/FAIL/ACCEPT/REJECT -- accepted
- `VerdictPayload` with invalid verdict string -- rejected with validation error
- `EvidenceItem` with type="test_output" and content="..." -- accepted
- `EvidenceItem` with type="screenshot" and path="/tmp/x.png" -- accepted
- `CriterionResult` with criterion="X" and result="PASS" -- accepted
- `CriterionResult` missing required `criterion` field -- rejected

### Unit: Orchestrator fallback logic

- Mock `get_verdict` to return a structured PASS -- verify `_run_pipeline_step` uses it (does not call `parse_verdict`)
- Mock `get_verdict` to return `None` -- verify `_run_pipeline_step` falls back to `parse_verdict` on the raw text
- Mock `get_verdict` to return a structured REJECT with feedback -- verify `StepResult.feedback` is populated from the structured data

### Integration: Full pipeline with structured verdicts

- Run the happy-path pipeline test where mock agents create verdict events via `submit_verdict` instead of returning "VERDICT: PASS" text -- verify the pipeline completes to "done"
- Run a QA rejection loop where QA submits a structured FAIL verdict with criteria_results showing which criterion failed -- verify the feedback is passed to the SWE agent on retry
- Run a mixed scenario: grooming agent returns free text (no verdict event), implementing agent returns free text, QA agent submits structured verdict -- verify the orchestrator handles the mix correctly

### Integration: Evidence storage

- Submit a verdict with 3 evidence items, then retrieve via `get_verdict` -- verify all evidence items are present in the returned data
- Submit a verdict with criteria_results, then retrieve -- verify criteria_results are intact with criterion names and PASS/FAIL results

## Log

### [SWE] 2026-03-28 12:00
- Created `backend/codehive/core/verdicts.py` with Pydantic models (VerdictPayload, EvidenceItem, CriterionResult, VerdictValue enum) and DB operations (submit_verdict, get_verdict)
- Updated `backend/codehive/core/orchestrator_service.py`:
  - Added `evidence`, `criteria_results`, `feedback` fields to StepResult dataclass
  - Updated `_run_pipeline_step` to check for structured verdict via get_verdict() first, falling back to regex parse_verdict() when no structured verdict exists
  - Updated `build_instructions` for "testing" and "accepting" steps to include submit_verdict guidance
  - Updated rejection feedback to prefer structured feedback over raw output
  - Preserved existing `parse_verdict` function as backward-compatible fallback
- Created `backend/tests/test_verdicts.py` with 29 tests covering:
  - Pydantic model validation (6 tests): valid verdicts, invalid verdict string, full payload, evidence items, criterion results
  - submit_verdict (4 tests): basic PASS, all fields, invalid verdict, invalid session
  - get_verdict (3 tests): existing verdict, no verdict returns None, returns most recent
  - Orchestrator fallback (3 tests): structured verdict used when available, fallback to regex, structured REJECT populates feedback
  - Evidence storage (2 tests): evidence items round-trip, criteria_results round-trip
  - build_instructions guidance (3 tests): testing/accepting mention submit_verdict, implementing does not
  - StepResult fields (2 tests): defaults, all fields populated
- Files modified: backend/codehive/core/verdicts.py (new), backend/codehive/core/orchestrator_service.py, backend/tests/test_verdicts.py (new)
- Tests added: 29 new tests
- Build results: 2310 tests pass, 0 fail, ruff clean
- Known limitations: none

### [QA] 2026-03-28 13:30
- Tests: 29 new in test_verdicts.py, all 29 passed. Full suite: 2310 passed, 0 failed, 3 skipped.
- Ruff check: clean ("All checks passed!")
- Ruff format: clean ("286 files already formatted")
- Acceptance criteria:
  1. submit_verdict creates Event with type="verdict" and structured data (verdict, role, task_id): PASS
  2. get_verdict retrieves most recent verdict event, returns data dict or None: PASS
  3. Pydantic models VerdictPayload, EvidenceItem, CriterionResult validate schema correctly: PASS
  4. _run_pipeline_step reads structured verdict first, falls back to parse_verdict: PASS
  5. StepResult includes evidence, criteria_results, feedback fields: PASS
  6. build_instructions for testing/accepting includes submit_verdict guidance: PASS
  7. parse_verdict regex function preserved as fallback: PASS
  8. 10+ new tests, all existing tests green (29 new, 2310 total): PASS
  9. ruff check clean: PASS
- VERDICT: PASS

### [PM] 2026-03-28 14:15
- Reviewed diff: 3 files changed (verdicts.py new, test_verdicts.py new, orchestrator_service.py modified)
- Results verified: real data present -- 29/29 tests pass locally, ruff clean
- Acceptance criteria:
  1. submit_verdict creates Event with type="verdict" and structured data (verdict, role, task_id): MET -- verdicts.py L79-125, validates via Pydantic, creates Event row, commits
  2. get_verdict retrieves most recent verdict for session, returns data dict or None: MET -- verdicts.py L128-143, orders by created_at desc, limit 1
  3. Pydantic models VerdictPayload, EvidenceItem, CriterionResult validate correctly: MET -- VerdictValue enum restricts to PASS/FAIL/ACCEPT/REJECT, field validators reject empty strings
  4. _run_pipeline_step reads structured verdict first, falls back to parse_verdict: MET -- orchestrator_service.py L527-550, checks get_structured_verdict then parse_verdict
  5. StepResult includes evidence, criteria_results, feedback fields: MET -- orchestrator_service.py L63-65
  6. build_instructions for testing/accepting includes submit_verdict guidance: MET -- lines 195-200 and 212-216
  7. parse_verdict regex preserved as fallback: MET -- lines 96-117 unchanged
  8. 10+ new tests, all existing green (29 new, 2310 total): MET -- confirmed locally
  9. ruff check clean: MET -- confirmed locally
- All 9 acceptance criteria met, no gaps, no descoping
- Follow-up issues created: none needed
- VERDICT: ACCEPT
