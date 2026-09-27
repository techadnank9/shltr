# Status board

Update this file when you claim, finish or block on a workstream, in the same PR as the work. Newest log entries go at the top.

## Workstreams

Parts are defined in [PLAN.md](PLAN.md). Each part is one branch and one PR.

| Part | Folder | Owner | Branch | State | Notes |
|---|---|---|---|---|---|
| 1 · Vultr connection check | `infra/` | Rikin | `rikin/part1-vultr-check` | Done | Merged in PR #2. Account reachable ($300 credit), glm-5.3 T1–T3 pass |
| 2 · Photo to 3D room, on a laptop | `sandboxes/photo/` | Adnan | `adnan/part2-photo-to-3d` | Done | Merged in PR #3. Room test passed on Rikin's laptop: 33 s, network off, correct depth map (see log) |
| 3 · Vultr servers, teardown, smoke tests | `infra/` | Rikin | `rikin/part3-vultr-servers` | In review | **Servers are live** (about $0.18/hour). Smoke tests T4, T5, T7: 8/8 pass. See `infra/README.md` |
| 4 · Photo and video sandbox in a microVM, runner | `sandboxes/`, `backend/runner/` | Rikin | `rikin/part4-runner` | Done | Runner live on VM 2 (10.40.0.4:8700). 11/11 checks: photo 7.7 s, video 8.1 s with 6 stills, corrupted file fails cleanly, nothing left |
| Photo quality + FEMA dataset | `sandboxes/photo/`, `datasets/` | Rikin's helper agent | `rikin/photo-quality` | Done | Large depth model, photo texture, 7x denser mesh, sanitized `photo.jpg`; 5 public-domain FEMA interiors in `datasets/`. `shltr-photo:latest` on VM 2 updated; runner test 11/11 |
| 6 · Control plane on VM 1 | `backend/control/` | Rikin | `rikin/part6-control` | Done | **Live at https://45-76-251-95.sslip.io** (`/start` to upload). Real FEMA photo end to end in 38 s: 3D room, 6 damage items from glm-5.3, Pattern A code passed, $2,510 estimate, both sandboxes destroyed (E1–E7 pass) |
| 5 · Front end: 3D scene on fake events | `frontend/` | Adnan | `adnan/part5-frontend` | Done | Merged (PR #7). Vite + React + R3F on the EVENTS.md contract; fake player plays the whole case with the real `room.glb`; `?source=ws` ready for the control plane. Build verified on Rikin's laptop |
| 7a · Mock aid portal and fake scam site | `sites/` | Adnan | `adnan/part7a-portal-and-scam-site` | Next for Adnan | Plain HTML; spec in PLAN.md |

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

- **2026-09-27 · Rikin's agent:** Part 6 done and live at https://45-76-251-95.sslip.io. Control plane on VM 1 (FastAPI behind Caddy HTTPS) serves Adnan's front end, `/start` upload page, WebSocket with replay, and proxies assets from the runner. Runner gained `POST /jobs/code` (Pattern A) and `geom.py`. End-to-end test on FEMA `liberty-ky.jpg` through the public URL: 7/7 in 38 s (3D room 268k vertices in 22.9 s; glm-5.3 found 6 items; its measuring script passed on attempt 1 in a 3 s microVM; total $2,510 ±25%; 2 sandboxes started, 2 destroyed). Fixed: glm-5.3 returned an empty answer when its hidden reasoning used up 1,500 tokens (D24). Also: my branch switch had moved the helper agent's shared checkout; we now use separate worktrees (`.worktrees/`, excluded locally).
- **2026-09-27 · Rikin's helper agent:** Photo quality + FEMA dataset (`rikin/photo-quality`). `datasets/fema-interiors/manifest.json` lists 5 public-domain FEMA photos of flood-damaged rooms from Wikimedia Commons (checked by eye: indoor; licence from the Commons API); `datasets/fetch.py` downloads them. `depth.py` now uses Depth Anything V2 Metric-Indoor Large, textures the mesh with the photo (2048 px JPEG) and builds it on a 640 px grid: 5 FEMA photos in a microVM took 22.5-24.1 s each (was 7.8 s), 254-268k vertices (was 44k), 11.6-12.4 MB `room.glb` (was 1.7 MB). `prepare.py` writes a metadata-free `photo.jpg` (`stats.photo_file`) for the control plane. `shltr-photo:latest` on VM 2 is the new image (old one kept as `shltr-photo:prev` and `/srv/shltr/shltr-photo.prev.tar`); runner test 11/11, photo 26.0 s, video 25.9 s. Sample output: `design/samples/fema-belfry-ky.*`.
- **2026-09-27 · Rikin's agent:** Part 4 done. `shltr-photo` image (now with ffmpeg and `prepare.py` for video) built on VM 2 in 83 s and loaded into Microsandbox. Runner deployed as a systemd service on VM 2's private IP with a token shared only with VM 1. From VM 1: wrong token 401; photo → 3D room in 7.7 s (38,104 vertices) inside a fresh microVM; 10 s video → sharpest frame at 4 s → 3D room plus 6 stills in 8.1 s; corrupted .mp4 fails cleanly and its sandbox is still destroyed; 0 sandboxes left. Fixed along the way: microVM output folder needed `uid=10001,gid=10001` on the mount. EVENTS.md is now v1: `frames.ready`, video fields, and Adnan's five suggestions from PR #7.
- **2026-09-27 · Adnan's agent:** Part 5 in review (`adnan/part5-frontend`): `frontend/` Vite + React + TypeScript + React Three Fiber app driven only by `docs/EVENTS.md` events through one zustand reducer. Fake source replays `src/demo/case-0927a.json` (play, pause, replay, jump-to-stage, `&at=`); WebSocket source targets `/ws/cases/{id}`. Scene: photo → depth point cloud → real `room.glb`, 6 damage markers on the room's surfaces, glass sandbox, CONTAINED hit on the fake aid site, form steps with screenshots, approve / not yet, receipt. Build clean, full run with no console errors, 60 fps, works at 400 px.
- **2026-09-27 · Rikin's agent:** Part 3 done. Created in Atlanta: VPC `shltr-vpc` 10.40.0.0/24, VM 1 `vc2-2c-4gb` (45.76.251.95 / 10.40.0.3), VM 2 `vx1-g-4c-16g-240s` (64.177.43.236 / 10.40.0.4), two firewall groups, SSH key. Microsandbox 0.7.3 installed on VM 2 (`msb doctor` ready). Smoke tests 8/8: sandbox kernel 6.12.109 vs host 6.8.0 (own kernel), 1 CPU limit, `--no-net` blocks outbound, endless loop killed at 15 s, nothing left, VM 2 closed on 22/80/443 from the internet, VM 1 reaches VM 2 privately. Found and fixed: VM 2's SSH was reachable from the internet (Vultr firewall group not filtering the VX1, Ubuntu `ufw` allowing 22), so VM 2 now accepts traffic only on its private interface (D17).
- **2026-09-27 · Rikin's agent:** Part 2 room test **passed**. Test image: a flooded living room generated with Vultr's `z-image-turbo` (1792x1024, test use only). Exact PLAN.md command (network none, read-only, 2 GB, 2 CPUs) on Docker Desktop, Windows x86_64: 33.5 s total, depth 1.34–8.67 m, median 4.84 m, 38,104 vertices, 74,520 faces. The depth map correctly separates the doorframe, floor, sofa and back wall. Note for Part 4: this is slower than the 4 s gradient test because it's a real image on 2 CPUs; expect faster on VM 2 with 4 CPUs. Part 5 (front end) assigned to Adnan.
- **2026-09-27 · Adnan's agent:** Part 2 merged by Adnan without Rikin's review (PR #3): photo sandbox with Depth Anything V2 metric indoor small baked in; one photo in, `depth.png`, `room.glb` (metres, y up, -z forward) and `stats.json` out, with the network off, a read-only root and 2 GB. Offline run passes in ~4 s on a placeholder image; **real-room photo test still pending**.
- **2026-09-27 · Rikin's agent:** Part 1 passed. `check_vultr.py` reads the account (credit $300, pending $0) and lists 44 Atlanta plans including VX1. `check_inference.py`: T1 chat, T2 image, T3 tool call all PASS on glm-5.3 (0.8 s, 4.4 s, 1.1 s). Added docs/VULTR.md with inference prices. PR opened.
- **2026-09-27 · Rikin's agent:** Added PLAN.md. Work is split into small tested parts: Part 1 (Rikin, Vultr connection check) and Part 2 (Adnan, photo to 3D room in a no-network container) start now.
- **2026-09-27 · Rikin's agent:** PR `rikin/team-docs-and-design-sync`: added CLAUDE.md, STATUS.md, DECISIONS.md, ARCHITECTURE.md and EVENTS.md; brought both design pages up to date (glm-5.3, fake aid website containment scene, Sheltr branding).
- **2026-09-27 · Rikin's agent:** Moved to the main repo `techadnank9/shltr`. Initial commit: README, `.gitignore`, `.env.example`, 3D mockup and architecture blueprint.
