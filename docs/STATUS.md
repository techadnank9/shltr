# Status board

Update this file when you claim, finish or block on a workstream, in the same PR as the work. Newest log entries go at the top.

## Workstreams

Parts are defined in [PLAN.md](PLAN.md). Each part is one branch and one PR.

| Part | Folder | Owner | Branch | State | Notes |
|---|---|---|---|---|---|
| 1 · Vultr connection check | `infra/` | Rikin | `rikin/part1-vultr-check` | Done | Merged in PR #2. Account reachable ($300 credit), glm-5.3 T1–T3 pass |
| 2 · Photo to 3D room, on a laptop | `sandboxes/photo/` | Adnan | `adnan/part2-photo-to-3d` | Done | Merged in PR #3. Room test passed on Rikin's laptop: 33 s, network off, correct depth map (see log) |
| 3 · Vultr servers, teardown, smoke tests | `infra/` | Rikin | `rikin/part3-vultr-servers` | In review | **Servers are live** (about $0.18/hour). Smoke tests T4, T5, T7: 8/8 pass. See `infra/README.md` |
| 4 · Photo sandbox in a microVM, runner | `sandboxes/`, `backend/runner/` | Unassigned | | Not started | After Parts 2 and 3 |
| 5 · Front end: 3D scene on fake events | `frontend/` | Adnan | `adnan/part5-frontend` | Not started | Loads Part 2's `room.glb`; follows `docs/EVENTS.md` and `design/3d-mockup.html` |

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

- **2026-09-27 · Rikin's agent:** Part 3 done. Created in Atlanta: VPC `shltr-vpc` 10.40.0.0/24, VM 1 `vc2-2c-4gb` (45.76.251.95 / 10.40.0.3), VM 2 `vx1-g-4c-16g-240s` (64.177.43.236 / 10.40.0.4), two firewall groups, SSH key. Microsandbox 0.7.3 installed on VM 2 (`msb doctor` ready). Smoke tests 8/8: sandbox kernel 6.12.109 vs host 6.8.0 (own kernel), 1 CPU limit, `--no-net` blocks outbound, endless loop killed at 15 s, nothing left, VM 2 closed on 22/80/443 from the internet, VM 1 reaches VM 2 privately. Found and fixed: VM 2's SSH was reachable from the internet (Vultr firewall group not filtering the VX1, Ubuntu `ufw` allowing 22), so VM 2 now accepts traffic only on its private interface (D17).
- **2026-09-27 · Rikin's agent:** Part 2 room test **passed**. Test image: a flooded living room generated with Vultr's `z-image-turbo` (1792x1024, test use only). Exact PLAN.md command (network none, read-only, 2 GB, 2 CPUs) on Docker Desktop, Windows x86_64: 33.5 s total, depth 1.34–8.67 m, median 4.84 m, 38,104 vertices, 74,520 faces. The depth map correctly separates the doorframe, floor, sofa and back wall. Note for Part 4: this is slower than the 4 s gradient test because it's a real image on 2 CPUs; expect faster on VM 2 with 4 CPUs. Part 5 (front end) assigned to Adnan.
- **2026-09-27 · Adnan's agent:** Part 2 merged by Adnan without Rikin's review (PR #3): photo sandbox with Depth Anything V2 metric indoor small baked in; one photo in, `depth.png`, `room.glb` (metres, y up, -z forward) and `stats.json` out, with the network off, a read-only root and 2 GB. Offline run passes in ~4 s on a placeholder image; **real-room photo test still pending**.
- **2026-09-27 · Rikin's agent:** Part 1 passed. `check_vultr.py` reads the account (credit $300, pending $0) and lists 44 Atlanta plans including VX1. `check_inference.py`: T1 chat, T2 image, T3 tool call all PASS on glm-5.3 (0.8 s, 4.4 s, 1.1 s). Added docs/VULTR.md with inference prices. PR opened.
- **2026-09-27 · Rikin's agent:** Added PLAN.md. Work is split into small tested parts: Part 1 (Rikin, Vultr connection check) and Part 2 (Adnan, photo to 3D room in a no-network container) start now.
- **2026-09-27 · Rikin's agent:** PR `rikin/team-docs-and-design-sync`: added CLAUDE.md, STATUS.md, DECISIONS.md, ARCHITECTURE.md and EVENTS.md; brought both design pages up to date (glm-5.3, fake aid website containment scene, Sheltr branding).
- **2026-09-27 · Rikin's agent:** Moved to the main repo `techadnank9/shltr`. Initial commit: README, `.gitignore`, `.env.example`, 3D mockup and architecture blueprint.
