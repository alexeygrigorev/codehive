# 39: Mobile-Optimized Responsive Layouts

## Description
Optimize the web app for mobile screens. The mobile view is a "control tower" -- not an IDE. Focused on monitoring progress, answering questions, approving actions, viewing diff summaries, and quick task creation.

## Scope
- `web/src/layouts/MobileLayout.tsx` -- Mobile-specific layout with bottom navigation
- `web/src/pages/mobile/` -- Mobile-optimized page variants (dashboard, session summary, approvals, questions)
- `web/src/components/mobile/QuickActions.tsx` -- Quick action buttons (approve, answer, stop)
- `web/src/components/mobile/DiffSummary.tsx` -- Compact diff summary for mobile
- `web/src/hooks/useResponsive.ts` -- Hook for responsive breakpoint detection

## Dependencies
- Depends on: #14 (React app scaffolding)
- Depends on: #15 (project dashboard)
- Depends on: #16 (session chat)
- Depends on: #20 (approval UI)
