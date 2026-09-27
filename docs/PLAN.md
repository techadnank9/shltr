# Build plan: small parts, each tested, each its own PR

We build Shltr in small parts. Each part has one owner, one branch, a test that proves it works, and one PR. Nothing merges until its test passes and the other person has looked at the PR.

## How every part works

1. `git checkout main && git pull --rebase`
2. Create the part's branch (named below).
3. Build only what the part lists. Stay in its folder.
4. Run the part's test. Paste the output into the PR description.
5. Update `docs/STATUS.md` (state and a log line) in the same PR.
6. Open the PR. The other person reviews and merges.

## Part 1 · Vultr connection check · owner: Rikin

**Goal:** prove our Vultr account, API key and inference key work, and see real prices, **without creating any servers**.

- Branch: `rikin/part1-vultr-check`
- Folder: `infra/`
- Build:
  - `infra/check_vultr.py`: read-only calls to the Vultr API. Prints the account's credit balance and pending charges, whether the Atlanta region exists, and the VX1 and Cloud Compute plans available there with hourly and monthly prices.
  - `infra/check_inference.py`: three calls to `glm-5.3` on Vultr Serverless Inference: plain chat (T1), an image of a room (T2), a tool call (T3).
  - Both read keys from `.env` in the repo root and never print them.
- Test:
  ```
  python infra/check_vultr.py
  python infra/check_inference.py
  ```
  Passes when `check_vultr.py` prints the balance and a price table, and `check_inference.py` prints `PASS` for T1, T2 and T3.
- Cost: $0 for the API checks, a fraction of a cent for the three model calls.

## Part 2 · Photo to 3D room, on a laptop · owner: Adnan

**Goal:** prove the hardest piece works: one real photo of a room goes in, a 3D file comes out, **inside a locked-down container with no network**. This runs on a laptop with Docker; it moves into a Vultr microVM later.

- Branch: `adnan/part2-photo-to-3d`
- Folder: `sandboxes/photo/`
- Build:
  - `sandboxes/photo/Dockerfile`: Python image with Depth Anything V2 (metric, indoor, small), numpy, Pillow, trimesh. **Download the model weights during `docker build`**, because the container runs with the network off.
  - `sandboxes/photo/depth.py`: reads a photo from `/in`, writes to `/out`:
    - `depth.png` (the depth map, for a quick look)
    - `room.glb` (a coloured 3D point cloud or mesh in metres)
    - `stats.json`: `{"width": 518, "height": 392, "median_depth_m": 3.1, "vertices": 48211, "seconds": 7.4}`
  - `sandboxes/photo/README.md`: how to build and run it.
- Test: use your own photo of a room (we must have the rights to any photo we use).
  ```
  docker build -t shltr-photo sandboxes/photo
  docker run --rm --network none --read-only --memory 2g --cpus 2 \
    --tmpfs /tmp -v "$PWD/test-photos:/in:ro" -v "$PWD/out:/out" shltr-photo
  ```
  Passes when it finishes in under 60 seconds with the network off, and `out/room.glb` opens in a glTF viewer (for example https://gltf-viewer.donmccurdy.com) and looks like the room.
- Keep test photos and outputs out of git (`test-photos/` and `out/` are local only).

## Part 5 · Front end: the 3D case scene on fake events · owner: Adnan

**Goal:** the cinematic front end from `design/3d-mockup.html`, rebuilt as a real app that loads a **real** `room.glb` and is driven only by the events in `docs/EVENTS.md`. The backend doesn't exist yet, so a fake event player feeds it. When the backend is ready, only the event source changes.

- Branch: `adnan/part5-frontend`
- Folder: `frontend/`
- Build:
  - A Vite + React + three.js (React Three Fiber, drei) app in `frontend/`.
  - `frontend/src/events/fakeCase.ts`: a scripted list of events that follows `docs/EVENTS.md` exactly (envelope with `type`, `case_id`, `seq`, `ts`, `data`), covering one full case: `case.created` → `sandbox.started` → `log.line` → `depth.ready` → `code.attempt` (one failed try, then passed) → 4–6 × `damage.found` → `estimate.total` → `threat.contained` (fake aid website: prompt injection, download, exfiltration) → `form.step` × 4 → `approval.needed`.
  - An event source interface with two implementations: the fake player (with timing) and a WebSocket client for `/ws/cases/{id}` (it can stay unused for now).
  - Scene: loads `room.glb` from `depth.ready.glb_url`, places `damage.found` markers at `position` (metres, `room.glb` coordinates), shows the sandbox boundary and plays the containment effect on `threat.contained`. Includes the log panel, the damage ledger with a running total, and the approval panel with Approve / Not yet sending `approve` / `decline`.
  - Use the sample room at `design/samples/flooded-room.glb` (real Part 2 output) as the fake `glb_url`.
- Test:
  ```
  cd frontend && npm install && npm run dev
  ```
  Passes when a full fake case plays from start to finish without errors in the console, the real sample room renders and can be orbited, markers sit on the room's surfaces, and Approve changes the state. `npm run build` must also succeed.
- Visual direction: follow `design/3d-mockup.html` (dark storm palette, amber accent, red for damage and alarms, Big Shoulders Display, IBM Plex Sans and Mono). Blender assets can come later in their own part.

## Design reference

- 3D front-end concept: [design/3d-mockup.html](../design/3d-mockup.html)
- Architecture diagrams: [design/blueprint.html](../design/blueprint.html)

Open either file in a browser. They are the latest designs: Sheltr branding, `glm-5.3`, and the fake aid website as the containment scene. Rikin also has private preview links to the same pages; the files in `design/` are the source of truth.

## Next parts (after 1 and 2 merge)

| Part | What | Depends on |
|---|---|---|
| 3 | Create VM 1, VM 2, VPC, firewalls on Vultr; teardown script; smoke tests T4–T8 | Part 1 |
| 4 | Move Part 2's container into a Microsandbox microVM on VM 2, plus the runner service | Parts 2 and 3 |
| 5 | Front end: React + three.js scene driven by fake events from `docs/EVENTS.md`, loading Part 2's `room.glb` | Part 2 |
| 6 | Control plane: planner on `glm-5.3`, Pattern A retry loop, WebSocket events | Parts 1 and 4 |
| 7 | Browser sandbox, mock aid portal, fake scam page, approval gate | Part 6 |
| 8 | Demo video, README, submission | Everything |
