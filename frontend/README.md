# Sheltr front end

The 3D case scene from `design/3d-mockup.html`, as a real app. It is driven only by the live events in [`docs/EVENTS.md`](../docs/EVENTS.md). It loads the **real** `room.glb` from the depth model (Part 2).

## Run

```
cd frontend
npm install
npm run dev          # http://localhost:5173/?source=fake
npm run build        # type-check + production build into dist/
```

## URL flags

| Flag | What it does |
|---|---|
| `?source=fake` (default) | Replays the scripted demo case in `src/demo/case-0927a.json`, with play, pause, replay and jump-to-stage (click a stage chip) |
| `&at=21` | Starts the fake case 21 seconds in (handy for screenshots and the demo video) |
| `?source=ws&case=c_0927a` | Connects to the control plane at `/ws/cases/{case_id}`. In dev, Vite proxies `/ws` to `VITE_API` (default `http://localhost:8000`). `&api=wss://host` points it somewhere else |

## How it fits together

```
EventSource (fake | ws) ──events──▶ store.ts: reduce(state, event, t) ──▶ components read the store
        ▲                                                                    │
        └──────────── approve / decline (source.send) ◀── Approve button ◀───┘
```

- `src/events/types.ts`: the contract from EVENTS.md, as TypeScript types.
- `src/events/fakeSource.ts` and `wsSource.ts`: the two event sources. `pick.ts` chooses one from the URL.
- `src/store.ts`: **one zustand store with one reducer** for every event type. Components never talk to the network.
- Every item in the store keeps `t`, the source clock when it arrived. Scene animations are "time since `t`", so pause, replay and jump all work without extra code.
- `src/scene/`: the React Three Fiber scene.
  - `Room`: `depth.ready` loads `room.glb`. The flat photo becomes a depth-coloured point cloud that pushes back into 3D, then the solid mesh fades in.
  - `Markers`: a pulsing marker and label per `damage.found`, at `position` in room.glb metres.
  - `Sandbox`: the glass boundary while a sandbox is alive, and the CONTAINED hit, flash and shockwave per `threat.contained`.
  - `CameraDirector`: the fly-through. It follows case state rather than a timeline, so the same code works for fake and live events. Dragging hands the camera to the viewer until the next stage.
  - Bloom and vignette come from `@react-three/postprocessing`.
- `src/ui/`: the stage chips, the sandbox log (including the Pattern A retry loop), the damage ledger, the aid form steps with screenshots, approval and receipt, and the photo, alarm and caption overlays.

## Demo assets (`public/demo/`)

| File | Source |
|---|---|
| `room.glb` | Real Part 2 output (`design/samples/flooded-room.glb`) |
| `photo.jpg` | The survivor photo rebuilt from `room.glb` vertex colours by `scripts/room_photo.py`, which also printed the damage marker positions |
| `form-*.svg`, `receipt.svg` | Screenshots of our own mock aid portal (it is not a real site) |

## Phone and motion

- At 900 px and narrower, the panels stack under the stage. Tested at 400 px wide with no horizontal scroll.
- `prefers-reduced-motion` turns off the camera flights, the point-cloud reveal, pulsing, rain, shockwaves and CSS animations. Every state still shows.
