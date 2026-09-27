# Status board

Update this file when you claim, finish or block on a workstream, in the same PR as the work. Newest log entries go at the top.

## Workstreams

Parts are defined in [PLAN.md](PLAN.md). Each part is one branch and one PR.

| Part | Folder | Owner | Branch | State | Notes |
|---|---|---|---|---|---|
| 1 · Vultr connection check | `infra/` | Rikin | `rikin/part1-vultr-check` | In progress | API key set; inference key still to add to `.env` |
| 2 · Photo to 3D room, on a laptop | `sandboxes/photo/` | Adnan | `adnan/part2-photo-to-3d` | In review | `sandboxes/photo/`: Depth Anything V2 metric indoor small, no network, ~5 s per photo |
| 3 · Vultr servers, teardown, smoke tests T4–T8 | `infra/` | Unassigned | | Not started | After Part 1 |
| 4 · Photo sandbox in a microVM, runner | `sandboxes/`, `backend/runner/` | Unassigned | | Not started | After Parts 2 and 3 |

## Later workstreams

| Workstream | Folder | Owner | State | Notes |
|---|---|---|---|---|
| Runner service on VM 2 | `backend/runner/` | Unclaimed | Not started | |
| Control plane on VM 1 | `backend/control/` | Unclaimed | Not started | Planner, retry loop, WebSocket |
| Browser sandbox, mock aid portal, fake scam page | `sandboxes/`, `backend/control/` | Unclaimed | Not started | |
| Front end (3D, React + three.js) | `frontend/` | Unclaimed | Not started | Build against fake events from EVENTS.md |
| Blender assets | `blender/` | Unclaimed | Not started | Blender not yet installed on Rikin's laptop |
| Demo video, README, submission | `docs/`, root | Unclaimed | Not started | Needs the containment moment on video |

States: Not started, In progress, Blocked, In review, Done.

## Log

- **2026-09-27 · Adnan's agent:** Part 2 in review (`adnan/part2-photo-to-3d`): photo sandbox image with Depth Anything V2 metric indoor small baked in; one photo in, `depth.png`, `room.glb` (metres, y up, -z forward) and `stats.json` out, with the network off, a read-only root and 2 GB.
- **2026-09-27 · Rikin's agent:** Added PLAN.md. Work is split into small tested parts: Part 1 (Rikin, Vultr connection check) and Part 2 (Adnan, photo to 3D room in a no-network container) start now.
- **2026-09-27 · Rikin's agent:** PR `rikin/team-docs-and-design-sync`: added CLAUDE.md, STATUS.md, DECISIONS.md, ARCHITECTURE.md and EVENTS.md; brought both design pages up to date (glm-5.3, fake aid website containment scene, Sheltr branding).
- **2026-09-27 · Rikin's agent:** Moved to the main repo `techadnank9/shltr`. Initial commit: README, `.gitignore`, `.env.example`, 3D mockup and architecture blueprint.
