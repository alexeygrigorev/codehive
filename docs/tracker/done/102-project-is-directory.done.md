# Issue #102: Project creation should ask for directory, not name

## Problem

The "Empty Project" button on the New Project page (`web/src/pages/NewProjectPage.tsx`) uses `prompt("Project name:")` and calls `createProject({ name })` via `POST /api/projects`. This is wrong because a project IS a directory -- the user should specify the filesystem path, and the name should be derived from the directory basename.

The backend already supports this via `POST /api/projects/by-path` (see `backend/codehive/api/routes/projects.py` line 64), which calls `get_or_create_project_by_path` in `backend/codehive/core/project.py`. The frontend simply does not use it.

## Scope

Frontend-only change. The backend `POST /api/projects/by-path` endpoint and `get_or_create_project_by_path` core function already exist and work correctly (they normalize the path, derive name from basename, and create-or-return the project). No backend changes are needed.

## Dependencies

None. The backend by-path endpoint already exists (shipped with issue #94a).

## Implementation Plan

### Step 1: Add `createProjectByPath` to `web/src/api/projects.ts`

Add a new API function that calls the existing `POST /api/projects/by-path` endpoint:

```typescript
export async function createProjectByPath(body: {
  path: string;
}): Promise<ProjectRead> {
  const response = await apiClient.post("/api/projects/by-path", body);
  if (!response.ok) {
    throw new Error(`Failed to create project: ${response.status}`);
  }
  return response.json() as Promise<ProjectRead>;
}
```

### Step 2: Replace the `handleCreateEmpty` function in `web/src/pages/NewProjectPage.tsx`

Currently (lines 55-72):
```typescript
async function handleCreateEmpty() {
  const name = prompt("Project name:");
  if (!name?.trim()) return;
  ...
  const project = await createProject({ name: name.trim() });
  ...
}
```

Replace the `prompt()` with a proper inline form. The form should have:

1. A **directory path** text input (required) with placeholder `/home/user/projects/myapp`
2. A **project name** text input (optional) with placeholder auto-filled from the path basename, and helper text "Leave empty to use directory name"
3. Client-side validation: path must start with `/` (absolute path check)
4. A "Create" button and a "Cancel" button

**UX flow:**
- User clicks "Empty Project" button
- The button area expands into the inline form (similar to how "From Notes" / "From Repository" already expand with a textarea -- see lines 158-185 in `NewProjectPage.tsx`)
- User enters a path like `/home/alexey/git/myapp`
- Name field auto-populates with `myapp` (last path segment)
- User can optionally change the name
- User clicks "Create"
- If the user provided a custom name, call the existing `POST /api/projects` with `{ name, path }` (the `ProjectCreate` schema already accepts `path`)
- If the user did NOT override the name (or left it as the auto-derived basename), call `POST /api/projects/by-path` with `{ path }` which auto-derives the name on the backend

**Simplification:** Since `POST /api/projects` already accepts both `name` and `path`, and the name is always known (either auto-derived on the frontend or user-provided), we can always use `POST /api/projects` with both `name` and `path` fields. This avoids needing to decide which endpoint to call. The `createProjectByPath` function from Step 1 is still useful as a cleaner alternative, but for the form we can use the simpler approach:

```typescript
const project = await createProject({
  name: derivedName,
  path: directoryPath,
});
```

Wait -- the current `createProject` function signature only sends `name` and optional `description`. We need to update it to also accept `path`.

### Step 2a: Update `createProject` in `web/src/api/projects.ts`

Change the function signature to accept `path`:

```typescript
export async function createProject(body: {
  name: string;
  path?: string;
  description?: string;
}): Promise<ProjectRead> {
```

This is a backward-compatible change since `path` is optional.

### Step 3: Update `NewProjectPage.tsx`

**Files to modify:** `web/src/pages/NewProjectPage.tsx`

Replace the `handleCreateEmpty` function and add the inline form UI.

**State to add:**
```typescript
const [showEmptyForm, setShowEmptyForm] = useState(false);
const [directoryPath, setDirectoryPath] = useState("");
const [projectName, setProjectName] = useState("");
const [pathError, setPathError] = useState<string | null>(null);
```

**Auto-derive name from path:** When `directoryPath` changes, auto-compute the basename and set `projectName` if the user has not manually edited it. Use a ref `userEditedName` to track whether the user manually changed the name.

```typescript
const [userEditedName, setUserEditedName] = useState(false);

// When directoryPath changes, auto-derive name (unless user manually edited)
useEffect(() => {
  if (!userEditedName && directoryPath.trim()) {
    const parts = directoryPath.replace(/\/+$/, "").split("/");
    const basename = parts[parts.length - 1] || "";
    setProjectName(basename);
  }
}, [directoryPath, userEditedName]);
```

**Validation:** Path must start with `/`.

**New handleCreateEmpty:**
```typescript
async function handleCreateEmpty() {
  setPathError(null);
  const trimmedPath = directoryPath.trim();
  if (!trimmedPath) {
    setPathError("Directory path is required");
    return;
  }
  if (!trimmedPath.startsWith("/")) {
    setPathError("Path must be absolute (start with /)");
    return;
  }
  const name = projectName.trim() || trimmedPath.replace(/\/+$/, "").split("/").pop() || "project";

  setLoading(true);
  setError(null);
  try {
    const project = await createProject({ name, path: trimmedPath });
    navigate(`/projects/${project.id}`);
  } catch (err) {
    setError(err instanceof Error ? err.message : "Failed to create project");
  } finally {
    setLoading(false);
  }
}
```

**UI replacement:** Replace the current "Empty Project" button (lines 132-142) with a button that toggles `showEmptyForm`, and render the inline form below it when `showEmptyForm` is true. The form should follow the same visual pattern as the "From Notes" / "From Repository" expanded section (lines 158-185).

Form HTML structure:
```tsx
{showEmptyForm && (
  <div className="mt-4 space-y-3 border dark:border-gray-600 rounded-lg p-4">
    <div>
      <label htmlFor="dir-path" className="block font-medium dark:text-gray-200 mb-1">
        Directory Path
      </label>
      <input
        id="dir-path"
        type="text"
        className="w-full border dark:border-gray-600 rounded p-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
        placeholder="/home/user/projects/myapp"
        value={directoryPath}
        onChange={(e) => setDirectoryPath(e.target.value)}
      />
      {pathError && <p className="text-red-600 text-sm mt-1">{pathError}</p>}
    </div>
    <div>
      <label htmlFor="proj-name" className="block font-medium dark:text-gray-200 mb-1">
        Project Name <span className="text-sm text-gray-500 dark:text-gray-400">(optional)</span>
      </label>
      <input
        id="proj-name"
        type="text"
        className="w-full border dark:border-gray-600 rounded p-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
        placeholder="Auto-derived from directory name"
        value={projectName}
        onChange={(e) => { setProjectName(e.target.value); setUserEditedName(true); }}
      />
    </div>
    <div className="flex gap-2">
      <button
        onClick={handleCreateEmpty}
        disabled={loading}
        className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
      >
        {loading ? "Creating..." : "Create Project"}
      </button>
      <button
        onClick={() => { setShowEmptyForm(false); setDirectoryPath(""); setProjectName(""); setPathError(null); setUserEditedName(false); }}
        className="px-4 py-2 rounded border dark:border-gray-600 text-gray-700 dark:text-gray-300"
      >
        Cancel
      </button>
    </div>
  </div>
)}
```

### Step 4: Remove the `prompt()` call entirely

The native browser `prompt()` (line 56) must be completely removed. All interaction happens through the inline form.

## Files to Modify

| File | Change |
|------|--------|
| `web/src/api/projects.ts` | Add `path?: string` to `createProject` body type. Optionally add `createProjectByPath` function. |
| `web/src/pages/NewProjectPage.tsx` | Replace `prompt()` with inline form. Add state for path/name/validation. Add `useEffect` for auto-deriving name. Update `handleCreateEmpty`. Add `useEffect` import if not present. |
| `web/src/test/NewProjectPage.test.tsx` | Add tests for the new form behavior (see Test Scenarios below). |
| `web/src/test/projects.test.ts` | Add test for `createProject` with `path` parameter. |

## Acceptance Criteria

- [ ] Clicking "Empty Project" on the New Project page shows an inline form with "Directory Path" and optional "Project Name" fields (no browser `prompt()`)
- [ ] Entering a path like `/home/user/git/myapp` auto-fills the project name with `myapp`
- [ ] User can manually override the auto-derived name
- [ ] Submitting with a non-absolute path (not starting with `/`) shows a validation error
- [ ] Submitting with an empty path shows a validation error
- [ ] Successful submission calls `POST /api/projects` with both `name` and `path` fields
- [ ] After successful creation, the user is navigated to the new project page
- [ ] The "Cancel" button hides the form and resets state
- [ ] Dark theme styling is consistent with existing form elements on the page
- [ ] `cd web && npx vitest run` passes with all existing + new tests passing

## Test Scenarios

### Unit: API layer (`web/src/test/projects.test.ts`)
- `createProject({ name, path })` sends POST to `/api/projects` with both `name` and `path` in the body

### Unit: NewProjectPage form (`web/src/test/NewProjectPage.test.tsx`)
- Clicking "Empty Project" shows the directory path input and project name input
- Entering a path auto-derives the project name from basename
- Submitting with empty path shows "Directory path is required" error
- Submitting with relative path (e.g., `foo/bar`) shows "Path must be absolute" error
- Submitting with valid absolute path calls `createProject` with correct name and path
- Clicking "Cancel" hides the form
- User can manually override the auto-derived name and the override is preserved
- Error message is displayed when `createProject` rejects

### Integration (manual, not automated)
- Create a project via the web UI by entering a real directory path
- Verify the project appears in the dashboard with the correct name and path
- Verify the project detail page shows the path

## Notes

- The session creation form "working directory" feature mentioned in the original issue requirements is OUT OF SCOPE for this issue. If needed, it should be tracked as a separate issue.
- The `POST /api/projects/by-path` endpoint is available as an alternative but not strictly needed since `POST /api/projects` already accepts `path`. The simpler approach is to always use `POST /api/projects` with both `name` and `path`.

## Log

### [SWE] 2026-03-18 15:55
- Added `path?: string` to `createProject` body type in `web/src/api/projects.ts`
- Replaced `prompt()` in `NewProjectPage.tsx` with inline form containing Directory Path input, optional Project Name input, Create/Cancel buttons
- Added `useEffect` for auto-deriving project name from path basename
- Added client-side validation (empty path, non-absolute path)
- Added `userEditedName` state to preserve manual name overrides
- Files modified: `web/src/api/projects.ts`, `web/src/pages/NewProjectPage.tsx`, `web/src/test/projects.test.ts`, `web/src/test/NewProjectPage.test.tsx`
- Tests added: 9 new tests (1 API test for createProject with path, 8 NewProjectPage form tests)
- Build results: TypeScript compiles clean, 19/19 tests pass in modified files, 598/601 total pass (3 pre-existing failures in ProjectPage.test.tsx unrelated to this change)
- Known limitations: none

### [QA] 2026-03-18 16:00
- TypeScript: compiles clean (npx tsc --noEmit)
- Tests: 604 passed, 0 failed (1 e2e suite fails due to Playwright config issue, unrelated)
- Acceptance criteria:
  - Inline form with Directory Path and Project Name fields (no prompt()): PASS
  - Path auto-derives project name from basename: PASS
  - User can manually override auto-derived name: PASS
  - Non-absolute path shows validation error: PASS
  - Empty path shows validation error: PASS
  - createProject sends both name and path: PASS
  - Navigation to project page after creation: PASS
  - Cancel button hides form and resets state: PASS
  - Dark theme styling consistent: PASS
  - All tests pass: PASS
- VERDICT: PASS

### [PM] 2026-03-18 16:05
- Reviewed diff: 4 files changed for issue #102 (projects.ts, NewProjectPage.tsx, NewProjectPage.test.tsx, projects.test.ts)
- Results verified: 607/607 tests pass, 0 failures
- Acceptance criteria: all 10 met
  - prompt() removed, replaced with inline form
  - Path auto-derives name from basename via useEffect
  - Manual name override preserved via userEditedName flag
  - Validation for empty and non-absolute paths
  - createProject sends name + path to POST /api/projects
  - Navigation after creation works
  - Cancel resets all state
  - Dark theme styling consistent
  - 9 new tests cover all specified test scenarios
- No scope creep in #102 files; other changes in working tree belong to issues #101, #103, #104
- Follow-up issues created: none needed
- VERDICT: ACCEPT
