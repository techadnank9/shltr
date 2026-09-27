# Status board

Update this file when you claim, finish or block on a workstream, in the same PR as the work. Newest log entries go at the top.

## Workstreams

| Workstream | Folder | Owner | State | Notes |
|---|---|---|---|---|
| Vultr account, credit, API and inference keys | (manual) | Rikin | In progress | Keys go in `.env` in the repo folder, never committed |
| Infrastructure: VPC, firewalls, VM 1, VM 2, teardown | `infra/` | Rikin's agent | Waiting on keys | Show hourly prices before creating anything |
| Smoke tests T1–T8 (see ARCHITECTURE.md) | `infra/` | Rikin's agent | Not started | Nothing else gets built on Vultr until these pass |
| Photo sandbox: depth model to `room.glb` | `sandboxes/` | Unclaimed | Not started | Riskiest piece, start early |
| Runner service on VM 2 | `backend/runner/` | Unclaimed | Not started | |
| Control plane on VM 1 | `backend/control/` | Unclaimed | Not started | Planner, retry loop, WebSocket |
| Browser sandbox, mock aid portal, fake scam page | `sandboxes/`, `backend/control/` | Unclaimed | Not started | |
| Front end (3D, React + three.js) | `frontend/` | Unclaimed | Not started | Build against fake events from EVENTS.md |
| Blender assets | `blender/` | Unclaimed | Not started | Blender not yet installed on Rikin's laptop |
| Demo video, README, submission | `docs/`, root | Unclaimed | Not started | Needs the containment moment on video |

States: Not started, In progress, Blocked, In review, Done.

## Log

- **2026-09-27 · Rikin's agent:** PR `rikin/team-docs-and-design-sync`: added CLAUDE.md, STATUS.md, DECISIONS.md, ARCHITECTURE.md and EVENTS.md; brought both design pages up to date (glm-5.3, fake aid website containment scene, Sheltr branding).
- **2026-09-27 · Rikin's agent:** Moved to the main repo `techadnank9/shltr`. Initial commit: README, `.gitignore`, `.env.example`, 3D mockup and architecture blueprint.
