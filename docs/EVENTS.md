# Live event contract

The control plane pushes these events to the front end over a WebSocket at `/ws/cases/{case_id}`. The front end must work from these events alone, so it can be built against fake events before the backend exists.

**v1** (adds video and the server rules below). Change it only in a small, clearly described PR, and tell the other agent's human.

## Envelope

Every event has the same outer shape:

```json
{
  "type": "damage.found",
  "case_id": "c_0927a",
  "seq": 14,
  "ts": "2026-09-27T09:41:07Z",
  "data": { }
}
```

- `seq` increases by 1 per case, so the front end can spot gaps.
- `ts` is UTC in ISO 8601.

## Events

| `type` | `data` fields | When |
|---|---|---|
| `case.created` | `photos: [{id, url}]`, `title` (e.g. the address, "14 Alder Lane, ground floor") | Upload accepted |
| `plan.ready` | `steps: [{id, title}]` | Planner produced a plan |
| `sandbox.started` | `sandbox_id, kind ("photo" or "browser"), limits: {cpus, memory_mb, timeout_s, network}` | Runner created a sandbox |
| `log.line` | `sandbox_id, stream ("stdout" or "stderr"), text` | Any output line. Lines from the planner itself use `sandbox_id: "control"` |
| `depth.ready` | `glb_url, vertices, median_depth_m`, plus `depth_url`, `source_kind` ("photo" or "video"), `seconds` | 3D room is ready to load |
| `frames.ready` | `duration_s, best_t, frames: [{url, t}]` | Video only: evidence stills with their time in the video (seconds); `best_t` is the frame the 3D room was built from |
| `code.attempt` | `attempt, code, status ("running", "failed", "passed"), stderr?` | Each Pattern A try |
| `damage.found` | `id, label, metric, cost_usd, position: [x, y, z]` | One damage item, position in `room.glb` coordinates (metres) |
| `estimate.total` | `cost_usd, range_pct` | Totals updated |
| `threat.contained` | `sandbox_id, kind ("prompt_injection", "download", "exfiltration", "timeout", "memory"), detail` | The sandbox blocked something |
| `link.checked` | `url, verdict ("scam", "legitimate", "unsure" or "not_checked"), reasons: [..], advice, screenshot_url` | After a `check_link` request: the page was opened in a browser microVM and judged by the vision model. `threat.contained` events for that page come just before it |
| `form.step` | `n, total, title, screenshot_url, verified (bool), note` | Each Pattern B step |
| `approval.needed` | `summary, amount_usd` | Paused before submit |
| `approval.result` | `approved (bool)` | Survivor answered |
| `claim.submitted` | `receipt_id, screenshot_url` | Submit done |
| `sandbox.destroyed` | `sandbox_id, lifetime_s` | Teardown proof |
| `case.error` | `message` | Something failed that the user should see |

## Server rules (agreed with the front end, PR #7)

- **Replay on connect:** when a client connects or reconnects to `/ws/cases/{case_id}`, the server re-sends the case's events from `seq` 1. The front end drops duplicates by `seq`, so a page reload rebuilds the scene.
- **`approval.result`** is sent immediately after the server receives `approve` or `decline`.
- **Asset URLs** (`photos[].url`, `glb_url`, `depth_url`, `frames[].url`, `screenshot_url`) are served from the same origin as the app, through VM 1. The browser never talks to VM 2.
- `sandbox.destroyed` is always sent for every `sandbox.started`, including after errors and timeouts.

## Client to server

| Message | Fields |
|---|---|
| `approve` | `case_id` |
| `decline` | `case_id` |
| `check_link` | `case_id, url` |
