# Runner (VM 2)

The runner is the only way work reaches the sandbox host. VM 1's control plane sends it a survivor's photo or video; the runner starts a **new microVM** for that one job, streams what happens, returns the 3D room and **destroys the microVM**.

```
VM 1 control plane ──(private network, token)──► runner on VM 2 (10.40.0.4:8700)
                                                   │ msb run --no-net --cpus 4 --memory 3072M --max-duration 180s
                                                   ▼
                                            microVM from shltr-photo:latest
                                            /in (read-only) ─► prepare.py ─► depth.py ─► /out
```

## API

All requests need `Authorization: Bearer <RUNNER_TOKEN>`. The token lives in `/etc/shltr/runner.env` on VM 2 and VM 1 (mode 600) and nowhere else.

| Call | What it does |
|---|---|
| `GET /health` | `{"ok", "microsandbox", "image", "sandboxes", "limits"}` |
| `POST /jobs/reconstruct` | Multipart `file` (photo or video, up to 100 MB) and optional `case_id`. Returns a live stream of newline-delimited JSON events |
| `GET /jobs/{job_id}/files/{path}` | Outputs: `room.glb`, `depth.png`, `stats.json`, `frames/frame_NN.jpg`. Paths can't escape the job's output folder |

Events use the `docs/EVENTS.md` types, as `{"type", "job_id", "data"}`. The control plane adds `case_id`, `seq` and `ts`:

| Event | Data |
|---|---|
| `sandbox.started` | `sandbox_id`, `kind: "photo"`, `input: "photo" or "video"`, `bytes`, `limits` |
| `log.line` | `sandbox_id`, `stream`, `text` |
| `depth.ready` | `glb_url`, `depth_url`, `vertices`, `median_depth_m`, `source_kind`, `seconds` |
| `frames.ready` | Video only: `duration_s`, `best_t`, `frames: [{url, t}]` |
| `case.error` | `sandbox_id`, `message` |
| `sandbox.destroyed` | `sandbox_id`, `lifetime_s`, `exit_code`. Always sent, even after a failure |

## Safety rules it enforces

- Listens on the private IP only; VM 2's firewall accepts nothing from the internet.
- The upload's file name is never used; only a checked extension survives (`input.mp4`).
- One job at a time (VM 2 has 4 CPUs), each in a fresh microVM with no network, 4 CPUs, 3 GB and a 180 s limit.
- The microVM is removed in a `finally` block, so it's destroyed on success, error and timeout alike.
- The output folder is mounted with `uid=10001,gid=10001`, so the image's non-root user can write it without making anything world-writable.

## Deploy and test

From the repo root:

```
tar -C backend -cf - runner | ssh -F infra/keys/ssh_config vm2 'mkdir -p /opt/shltr && tar -C /opt/shltr -xf -'
ssh -F infra/keys/ssh_config vm2 'bash -s' < infra/bootstrap/runner.sh
ssh -F infra/keys/ssh_config vm2 'cat /etc/shltr/runner.env' | ssh -F infra/keys/ssh_config vm1 'mkdir -p /etc/shltr && umask 077 && cat > /etc/shltr/runner.env'
# on VM 1, with a photo and a video in the current folder:
python3 test_runner.py flooded-room.png walkthrough.mp4
```

The photo image is built on VM 2 from `sandboxes/photo/` with `docker build -t shltr-photo`, then `docker save shltr-photo:latest -o shltr-photo.tar && msb load -i shltr-photo.tar`.

## Test result (Sept 27, VM 2 `vx1-g-4c-16g-240s`)

```
PASS  R1 wrong token refused             HTTP 401
PASS  R2 photo events in order           sandbox.started -> depth.ready -> sandbox.destroyed
PASS  R2 photo room.glb downloads        1469 KB, 38104 vertices, median 4.839 m
PASS  R2 photo sandbox destroyed         after 7.7 s
PASS  R3 video events in order           sandbox.started -> depth.ready -> frames.ready -> sandbox.destroyed
PASS  R3 video room.glb downloads        1444 KB, 37531 vertices, median 4.563 m
PASS  R3 video evidence stills           6 frames, sharpest at 4.0 s
PASS  R3 video sandbox destroyed         after 8.1 s
PASS  R4 fails cleanly                   sandbox.started -> case.error -> sandbox.destroyed
PASS  R4 sandbox still destroyed         (corrupted .mp4: "moov atom not found")
PASS  R5 nothing left running            0 sandboxes
11/11 checks passed
```

## Known limits

- `msb run` releases the job's output when the job ends, so `log.line` events arrive together at the end (after about 8 s) rather than one by one. Part 6 can switch to `msb create` plus `msb exec --stream` if live lines matter.
- Job folders in `/srv/shltr/jobs` are not cleaned up yet. Add an age-based cleanup before running many cases.
