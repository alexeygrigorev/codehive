# Issue #124: Project archetypes (Brainstorm, Guided Interview, etc.) don't work

## Problem

On the New Project page, clicking Brainstorm, Guided Interview, From Notes, or From Repository does nothing — only Empty Project works. These archetypes need to be implemented or removed.

## Requirements

- [ ] Decide which archetypes to keep and which to remove/defer
- [ ] For kept archetypes: implement the flow (what happens when you click each one?)
- [ ] For deferred archetypes: either hide them or show "Coming soon" state
- [ ] Think about how each archetype maps to the project creation flow:
  - **Brainstorm**: Free-form ideation → creates a project with brainstorm session?
  - **Guided Interview**: Step-by-step questions → builds a project spec?
  - **From Notes**: Paste notes → AI structures into project?
  - **From Repository**: Enter repo URL → clone and analyze?

## Notes

- These may be significant features on their own — PM should decide scope during grooming
- Consider: are these separate session modes within a project, or different project creation wizards?
