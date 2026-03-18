# Issue #96: Web UX rework -- navigation, layout, and overall experience

## Status

**Meta-issue.** This was split into focused sub-issues during grooming. Do not implement this file directly.

## Sub-issues

| Sub-issue | File | Scope |
|-----------|------|-------|
| #96a | `96a-navigation-sidebar-breadcrumbs.groomed.md` | Navigation sidebar with project/session tree + breadcrumb trail |
| #96b | `96b-session-page-cleanup.groomed.md` | Session page: replace raw timeline, collapsible right sidebar, layout cleanup |

## Descoped (covered by other issues)

| Requirement | Covered by |
|-------------|------------|
| Project page tabs (Sessions / Issues) | #95 (web project page redesign) |
| Dark theme support | #89 (dark theme) |
| Mobile-responsive layout | Already implemented (MobileLayout + MobileNav exist) |
| Dashboard improvements | Dashboard already shows session counts, loading states, error handling, and "New Project" button |

## Original problem

The web UI was built feature-by-feature and lacks cohesive UX:
- No consistent navigation (no back buttons, no breadcrumbs)
- No sidebar/nav showing projects and sessions
- Session page has no link back to the project
- Timeline sidebar shows raw events that aren't useful to the user
- Mode switcher, approval badges, history search are present but disorganized
