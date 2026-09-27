# Live event contract

The control plane pushes these events to the front end over a WebSocket at `/ws/cases/{case_id}`. The front end must work from these events alone, so it can be built against fake events before the backend exists.

**Draft v0.** Change it only in a small, clearly described PR, and tell the other agent's human.

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
| `case.created` | `photos: [{id, url}]` | Upload accepted |
| `plan.ready` | `steps: [{id, title}]` | Planner produced a plan |
| `sandbox.started` | `sandbox_id, kind ("photo" or "browser"), limits: {cpus, memory_mb, timeout_s, network}` | Runner created a sandbox |
| `log.line` | `sandbox_id, stream ("stdout" or "stderr"), text` | Any output line |
| `depth.ready` | `glb_url, vertices, median_depth_m` | 3D room is ready to load |
| `code.attempt` | `attempt, code, status ("running", "failed", "passed"), stderr?` | Each Pattern A try |
| `damage.found` | `id, label, metric, cost_usd, position: [x, y, z]` | One damage item, position in `room.glb` coordinates (metres) |
| `estimate.total` | `cost_usd, range_pct` | Totals updated |
| `threat.contained` | `sandbox_id, kind ("prompt_injection", "download", "exfiltration", "timeout", "memory"), detail` | The sandbox blocked something |
| `form.step` | `n, total, title, screenshot_url, verified (bool), note` | Each Pattern B step |
| `approval.needed` | `summary, amount_usd` | Paused before submit |
| `approval.result` | `approved (bool)` | Survivor answered |
| `claim.submitted` | `receipt_id, screenshot_url` | Submit done |
| `sandbox.destroyed` | `sandbox_id, lifetime_s` | Teardown proof |
| `case.error` | `message` | Something failed that the user should see |

## Client to server

| Message | Fields |
|---|---|
| `approve` | `case_id` |
| `decline` | `case_id` |
| `check_link` | `case_id, url` |
