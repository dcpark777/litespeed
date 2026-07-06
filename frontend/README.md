# frontend/

React + Vite SPA — a pure view over the FastAPI backend's HTTP/WS API
(SPEC §2). No Electron, no IPC, no direct filesystem access: if the UI needs
something, it's an API endpoint first.

**Status: placeholder scaffold.** Hackathon Tracks 1 (transcript pane) and
2 (workstream board) start here; SPEC §7 has the three-region layout and the
settled library table (TanStack Query/Router, zustand, @codemirror/merge,
Tailwind + Radix). Aesthetic: dense, keyboard-driven — glance, decide, next.

Build: `npm run build` outputs into `src/nova/static/` (wheel-embedded by CI's
tag build; `dist/` is never committed). Dev: `npm run dev` proxies to the
backend — auth is the per-launch bearer token printed by `nova up`.

The generated-from-OpenAPI TS client (`openapi-typescript` + `openapi-fetch`)
is the FE/BE contract — regenerate it when server Pydantic models change
rather than hand-writing request types.
