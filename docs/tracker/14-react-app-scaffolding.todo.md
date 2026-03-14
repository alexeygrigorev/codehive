# 14: React App Scaffolding

## Description
Set up the React web application in the `web/` directory with Vite, TypeScript, and Tailwind CSS. Create the basic app shell with routing, layout components, and API client configuration.

## Scope
- `web/` -- New React project via Vite (React + TypeScript template)
- `web/src/App.tsx` -- Root component with React Router
- `web/src/layouts/MainLayout.tsx` -- App shell with sidebar navigation
- `web/src/api/client.ts` -- Axios/fetch wrapper configured for the backend API
- `web/src/pages/` -- Placeholder page components (Dashboard, ProjectView, SessionView)
- `web/tailwind.config.js` -- Tailwind configuration
- `web/package.json` -- Dependencies: react, react-router-dom, tailwindcss, typescript

## Dependencies
- Depends on: #01 (backend API must exist to configure API client base URL)
